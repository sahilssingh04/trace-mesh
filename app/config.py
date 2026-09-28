"""Explicit resource budgets. File size is bytes, never a vague 'word limit'."""
import os
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_MB', '25')) * 1024 * 1024
MAX_GRAPH_EDGES = int(os.getenv('MAX_GRAPH_EDGES', '20000'))
MAX_ROWS = 50000
