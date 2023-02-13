from firebase import Auth, Db

email = "test@example.com"
password = "12345678"
displayName = "test"
phoneNumber = "0620000000"

user = Auth.create_user(email=email, password=password,
                        display_name=displayName)

Auth.set_custom_user_claims(user.uid, {"staff": True, "admin": True})

Db.collection('staffs').document(email).set(
    {"email": email, "role": "Administrator", "displayName": displayName, "phone_number": phoneNumber, "disabled": False})
