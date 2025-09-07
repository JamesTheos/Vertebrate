from fastapi import FastAPI, HTTPException

app = FastAPI()

# Fake-DB für MVP
fake_users = {
    "louis": {
        "subscriptions": [
            {"app_id": 1, "name": "Analytics", "active": True},
            {"app_id": 2, "name": "CRM", "active": True},
            {"app_id": 3, "name": "Billing", "active": False},
        ]
    },
    "bob": {
        "subscriptions": [
            {"app_id": 2, "name": "CRM", "active": True},
        ]
    }
}

# Variante 1: Liste aller Subscriptions
@app.get("/subscriptions/{username}")
def get_subscriptions(username: str):
    user = fake_users.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"subscriptions": user["subscriptions"]}


# Variante 2: Prüfen ob subscribed für eine App
@app.get("/subscriptions/{username}/{app_id}")
def check_subscription(username: str, app_id: int):
    user = fake_users.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    for sub in user["subscriptions"]:
        if sub["app_id"] == app_id and sub["active"]:
            return {"subscribed": True, "app_id": app_id, "app_name": sub["name"]}
    
    return {"subscribed": False, "app_id": app_id}
