python -m uvicorn load_balancer:app --host 0.0.0.0 --port 8000
# python -m uvicorn load_balancer:app --workers 100 --timeout-keep-alive 65 --host 0.0.0.0 --port 8000
