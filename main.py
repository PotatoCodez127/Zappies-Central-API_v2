# /main.py

import uvicorn
import os

print("DEBUG - Supabase URL is:", settings.SUPABASE_URL)
print("DEBUG - History Table is:", settings.DB_CONVERSATION_HISTORY_TABLE)

if __name__ == "__main__":
    # Get the port from the environment variable, default to 8000
    # This is important for deployment services like Heroku
    port = int(os.environ.get("PORT", 8000))

    # Run the Uvicorn server
    # It will look for the 'app' instance in the 'api.server' module
    uvicorn.run("api.server:app", host="127.0.0.1", port=port, reload=False)