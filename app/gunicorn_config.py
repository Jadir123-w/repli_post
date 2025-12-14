# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8080"
backlog = 2048

# Worker processes
workers = 1  # For memory-intensive applications, use fewer workers
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 300
keepalive = 2

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
errorlog = "-"
loglevel = "info"
accesslog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = None

# Server hooks
def on_starting(server):
    server.log.info("Starting Geraldine AI Agent API")

def on_exit(server):
    server.log.info("Shutting down Geraldine Gonzales AI Agent API")