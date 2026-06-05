"""
dependencies/__init__.py
------------------------
Shared FastAPI dependencies (e.g. auth guards, DB sessions, rate limiters).

Add dependency functions here as the project grows. Example usage in a router:

    from dependencies import get_current_user

    @router.get("/protected")
    def protected(user = Depends(get_current_user)):
        ...
"""

# No shared dependencies yet — placeholder for future use.
