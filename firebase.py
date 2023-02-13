import firebase_admin
from firebase_admin import credentials, db, firestore, storage, auth

cred = credentials.Certificate('serviceAccountKey.json')

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://au-parking-default-rtdb.asia-southeast1.firebasedatabase.app/',
    'storageBucket': "au-parking.appspot.com",
})

TempDb = db
Db: firestore.firestore.Client = firestore.client()
Storage = storage.bucket()
Auth = auth
