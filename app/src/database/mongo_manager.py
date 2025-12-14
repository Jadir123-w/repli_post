from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
from typing import List, Dict
import uuid
import logging
from app.utils.config import Config

load_dotenv()

class MongoManager:
    _client = None

    def __init__(self):
        if MongoManager._client is None:  # If there is no active connection, we create it
            try:
                MongoManager._client = MongoClient(Config.REPLI_MONGO_URI, serverSelectionTimeoutMS=5000)
                MongoManager._client.server_info()  # Verify the connection
                logging.info("Connected to MongoDB Atlas")
            except Exception as e:
                logging.error(f"Error connecting to MongoDB: {str(e)}")
                raise Exception("Could not connect to MongoDB. Check the connection string and network.")

        # Assign the established connection
        self.client = MongoManager._client
        self.db = self.client.agent_memory_repli_post
        self.agent_memory_repli_post = self.db.conversations_memory

    def get_cv_analysis(self, thread_id: str) -> dict:
        """Gets the saved CV analysis for a specific thread_id"""
        try:
            cv_analysis = self.db.cv_analysis.find_one({"thread_id": thread_id})
            if cv_analysis:
                # Log for diagnostic - see which fields exist
                cv_data = cv_analysis.get("cv_analysis", {})

                # Verify if we have data in the correct format
                if cv_data and isinstance(cv_data, dict) and 'data' in cv_data:
                    logging.info(f"CV found in correct format for thread_id: {thread_id}")
                    return cv_data  # Returns directly the cv_analysis object that contains 'data'
                elif 'cv_data' in cv_analysis:
                    # Old format - return in the new format for compatibility
                    logging.info(f"CV found in old format for thread_id: {thread_id}")
                    return {
                        "success": True,
                        "data": cv_analysis.get("cv_data", {}),
                        "timestamp": cv_analysis.get("timestamp", datetime.utcnow().isoformat())
                    }
                else:
                    logging.warning(f"CV found but without valid data for thread_id: {thread_id}")
                    return {"success": False, "error": "Invalid data format in the saved CV"}

            logging.info(f"No CV analysis found for thread_id: {thread_id}")
            return {"success": False, "error": "No CV analysis found for this user"}
        except Exception as e:
            logging.error(f"Error retrieving CV analysis from MongoDB: {str(e)}")
            return {"success": False, "error": str(e)}

    def save_cv_analysis(self, thread_id: str, cv_analysis: dict) -> bool:
        """Saves the CV analysis to the database with the correct format"""
        try:
            # Verify that cv_analysis has the expected structure
            if 'data' not in cv_analysis:
                logging.warning(f"Attempting to save CV without 'data' field for thread_id: {thread_id}")
                if 'cv_data' in cv_analysis:
                    # Migrate old format to new
                    logging.info("Migrating old CV format to new format")
                    cv_analysis['data'] = cv_analysis.pop('cv_data')

            # Ensure we have valid data before saving
            if not cv_analysis.get('data') and 'raw_text' in cv_analysis:
                logging.warning("CV without structured data. Saving with raw_text")
                # Ensure a minimal data field to prevent later problems
                cv_analysis['data'] = {
                    "note": "Data extracted from raw text",
                    "text": cv_analysis['raw_text'][:500] + "..."
                }

            # Log the complete object for diagnostics
            logging.info(f"Saving CV with data: {str(cv_analysis.get('data', {}))[:300]}...")

            # Save in MongoDB with the appropriate format
            self.db.cv_analysis.update_one(
                {"thread_id": thread_id},
                {"$set": {
                    "thread_id": thread_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "cv_analysis": cv_analysis  # Save complete cv_analysis as a nested document
                }},
                upsert=True
            )

            # Verify that it was saved correctly
            verification = self.db.cv_analysis.find_one({"thread_id": thread_id})
            if verification and "cv_analysis" in verification:
                logging.info(f"CV saved correctly for thread_id: {thread_id}")
                return True
            else:
                logging.warning(f"CV save verification failed for thread_id: {thread_id}")
                return False
        except Exception as e:
            logging.error(f"Error saving CV analysis to MongoDB: {str(e)}")
            return False

    def save_message(self, thread_id: str, user_name: str, role: str, content: str):
        """Saves a message to the user's conversation"""
        message = {
            'thread_id': thread_id,
            'user_name': user_name,
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow(),
            'status': 'active'  # New field for tracking
        }
        self.agent_memory_repli_post.insert_one(message)

    def get_conversation_history(self, thread_id: str, limit: int = None) -> List[Dict]:
        """Gets the conversation history"""
        query = {"thread_id": thread_id}
        # Use self.agent_memory_repli_post instead of self.messages_collection
        cursor = self.agent_memory_repli_post.find(query).sort("timestamp", 1)  # 1 for ascending, -1 for descending
        if isinstance(limit, int) and limit > 0:
            cursor = cursor.limit(limit)
        return list(cursor)

    def update_user_name(self, thread_id: str, user_name: str):
        """Updates the user name in all their messages"""
        self.agent_memory_repli_post.update_many(
            {'thread_id': thread_id},
            {'$set': {'user_name': user_name}}
        )

    def export_conversation(self, thread_id: str, format: str = 'txt'):
        """Exports the conversation in the specified format"""
        messages = self.get_conversation_history(thread_id)
        if not messages:
            return None

        if format == 'txt':
            filename = f"conversation_{thread_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                for msg in messages:
                    f.write(f"{msg['role']}: {msg['content']}\n")
            return filename

        return None

    def finalize_conversation(self, thread_id: str):
        """Marks the conversation as finalized in MongoDB"""
        self.agent_memory_repli_post.update_many(
            {'thread_id': thread_id},
            {'$set': {
                'status': 'completed',
                'end_time': datetime.utcnow()
            }}
        )

    def get_last_active_thread(self) -> str:
        """Gets the last active thread_id"""
        last_conversation = self.agent_memory_repli_post.find_one(
            {'status': 'active'},
            sort=[('timestamp', -1)]
        )
        return last_conversation['thread_id'] if last_conversation else None

    def get_active_conversation_info(self) -> dict:
        """Gets information of the last active conversation"""
        last_conversation = self.agent_memory_repli_post.find_one(
            {'status': 'active'},
            sort=[('timestamp', -1)]
        )
        if last_conversation:
            # Get all messages from this conversation for context
            messages = self.get_conversation_history(last_conversation['thread_id'])
            # Get context from context collection if available
            context_data = self.get_context(last_conversation['thread_id'])
            return {
                'thread_id': last_conversation['thread_id'],
                'user_name': last_conversation.get('user_name'),
                'last_timestamp': last_conversation['timestamp'],
                'context': messages,
                'user_location': context_data.get('user_location') if context_data else None,
                'is_latinamerica': context_data.get('is_latinamerica') if context_data else None
            }
        return None

    def get_conversation_by_user(self, user_name: str) -> dict:
        """Gets the last active conversation of a specific user"""
        query = {
            'user_name': user_name,
            'status': 'active'
        }
        last_conversation = self.agent_memory_repli_post.find_one(query, sort=[('timestamp', -1)])
        if last_conversation:
            return {
                'thread_id': last_conversation['thread_id'],
                'user_name': last_conversation['user_name'],
                'last_timestamp': last_conversation['timestamp']
            }
        return None
        
    def get_context(self, thread_id: str) -> dict:
        """Gets the context for a specific thread_id"""
        try:
            # Ensure we have a context collection
            if not hasattr(self.db, 'context'):
                self.db.create_collection('context')
                
            context = self.db.context.find_one({"thread_id": thread_id})
            if context:
                logging.info(f"Retrieved context from MongoDB for thread_id: {thread_id}")
                # Log location info for debugging
                if "user_location" in context:
                    logging.info(f"Context has location: {context['user_location']} (Latinoamérica: {context.get('is_latinamerica')})")
                return context
            else:
                logging.info(f"No context found in MongoDB for thread_id: {thread_id}")
                return None
        except Exception as e:
            logging.error(f"Error retrieving context from MongoDB: {str(e)}")
            return None
            
    def save_context(self, thread_id: str, context: dict) -> bool:
        """Saves the context to the database"""
        try:
            # Ensure we have a context collection
            if not hasattr(self.db, 'context'):
                self.db.create_collection('context')
                
            # Make sure thread_id is in the context
            context["thread_id"] = thread_id
            context["last_updated"] = datetime.utcnow().isoformat()
            
            # Log location info for debugging
            if "user_location" in context:
                logging.info(f"Saving context with location: {context['user_location']} (Latinoamérica: {context.get('is_latinamerica')})")
            
            # Log service sold info for debugging
            if "service_sold" in context:
                logging.info(f"Saving context with service sold: {context['service_sold']}")
                
            # Update or insert the context
            result = self.db.context.update_one(
                {"thread_id": thread_id},
                {"$set": context},
                upsert=True
            )
            
            # Verify the operation was successful
            if result.acknowledged:
                logging.info(f"Context saved successfully for thread_id: {thread_id}")
                return True
            else:
                logging.warning(f"Context save operation not acknowledged for thread_id: {thread_id}")
                return False
        except Exception as e:
            logging.error(f"Error saving context to MongoDB: {str(e)}")
            return False

    def get_or_create_user_thread(self, user_name: str) -> str:
        """Gets or creates a thread_id for a user"""
        existing_conv = self.get_conversation_by_user(user_name)
        if existing_conv:
            return existing_conv['thread_id']
        return str(uuid.uuid4())

    def save_user_info(self, user_info: dict) -> None:
        """Saves the user's information in the users collection"""
        try:
            self.db.users.update_one(
                {"thread_id": user_info["thread_id"]},
                {"$set": user_info},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error saving user info to MongoDB: {str(e)}")

    def get_summarized_context(self, thread_id: str, limit: int = 5) -> str:
        """Gets a summary of the conversation context"""
        messages = self.get_conversation_history(thread_id, limit)
        context = []
        for msg in messages:
            speaker = "User" if msg['role'] == "user" else "Geraldine"
            context.append(f"{speaker}: {msg['content']}")
        return "\n".join(context)

    def get_full_conversation_summary(self, thread_id: str) -> dict:
        """Gets a full summary of the conversation including user profile and topics discussed"""
        messages = self.get_conversation_history(thread_id)
        user_info = {}
        topics_discussed = set()
        last_context = ""

        for msg in messages:
            content = msg['content'].lower()

            # Detect user information
            if 'me llamo' in content or 'soy' in content:
                user_info['introduction'] = msg['content']

            # Detect work/profession mentions
            if 'ingeniero' in content or 'desarrollador' in content:
                user_info['profession'] = msg['content']

            # Detect technologies/skills
            if 'laravel' in content or 'django' in content or 'ia' in content:
                user_info['skills'] = msg['content']

            # Detect interests
            if 'me interesa' in content or 'busco' in content:
                user_info['interests'] = msg['content']

            # Save last context
            if msg['role'] == 'assistant':
                last_context = msg['content']

        return {
            'user_info': user_info,
            'topics_discussed': list(topics_discussed),
            'last_context': last_context,
            'full_history': messages
        }



    def get_messages(self, thread_id: str, limit: int = None) -> List[Dict]:
        """
        Gets the most recent messages from a conversation

        Args:
            thread_id (str): Conversation ID
            limit (int, optional): Message limit to get

        Returns:
            list: List of messages sorted by date (most recent first)
        """
        query = {"thread_id": thread_id, "role": {"$in": ["user", "assistant"]}}

        # Sort by timestamp descending (most recent first)
        cursor = self.agent_memory_repli_post.find(query).sort("timestamp", -1)

        # Apply limit if specified
        if limit:
            cursor = cursor.limit(limit)

        return list(cursor)

    def get_user_info(self, thread_id: str) -> Dict:
        """
        Gets user information by thread_id

        Args:
            thread_id (str): Conversation ID

        Returns:
            dict: User information or None if not found
        """
        try:
            user_info = self.db.users.find_one({"thread_id": thread_id})
            return user_info
        except Exception as e:
            logging.error(f"Error retrieving user info from MongoDB: {str(e)}")
            return None

    def get_context(self, thread_id: str) -> dict:
        """
        Get context data for a thread

        Args:
            thread_id (str): Thread ID

        Returns:
            dict: Context data or None if not found
        """
        try:
            # Create a new collection for storing context if it doesn't exist yet
            if 'context_data' not in self.db.list_collection_names():
                self.db.create_collection('context_data')

            context = self.db.context_data.find_one({"thread_id": thread_id})
            return context
        except Exception as e:
            logging.error(f"Error retrieving context from MongoDB: {str(e)}")
            return None

    def save_context(self, thread_id: str, context_data: dict) -> bool:
        """
        Save context data for a thread

        Args:
            thread_id (str): Thread ID
            context_data (dict): Context data to save

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Add thread_id to ensure we can query it later
            context_data["thread_id"] = thread_id
            context_data["last_updated"] = datetime.utcnow()

            # Create a new collection for storing context if it doesn't exist yet
            if 'context_data' not in self.db.list_collection_names():
                self.db.create_collection('context_data')

            self.db.context_data.update_one(
                {"thread_id": thread_id},
                {"$set": context_data},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error saving context to MongoDB: {str(e)}")
            return False

    def get_conversation_context(self, thread_id: str) -> dict:
        """
        Get conversation context for a thread

        Args:
            thread_id (str): Thread ID

        Returns:
            dict: Conversation context or None if not found
        """
        try:
            # Try to find in a dedicated collection first
            if 'conversation_context' in self.db.list_collection_names():
                context = self.db.conversation_context.find_one({"thread_id": thread_id})
                if context:
                    return context

            # Fall back to context_data if available
            if 'context_data' in self.db.list_collection_names():
                context = self.db.context_data.find_one({"thread_id": thread_id})
                if context:
                    return context

            return None
        except Exception as e:
            logging.error(f"Error retrieving conversation context from MongoDB: {str(e)}")
            return None

    def save_conversation_context(self, thread_id: str, context_data: dict) -> bool:
        """
        Save conversation context for a thread

        Args:
            thread_id (str): Thread ID
            context_data (dict): Context data to save

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Add thread_id to ensure we can query it later
            context_data["thread_id"] = thread_id
            context_data["last_updated"] = datetime.utcnow()

            # Create a new collection for storing conversation context if it doesn't exist yet
            if 'conversation_context' not in self.db.list_collection_names():
                self.db.create_collection('conversation_context')

            self.db.conversation_context.update_one(
                {"thread_id": thread_id},
                {"$set": context_data},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error saving conversation context to MongoDB: {str(e)}")
            return False
