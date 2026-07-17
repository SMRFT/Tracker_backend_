from Tracker.utils.db import get_tracker_db
db = get_tracker_db()
doc = db['Tracker_notification'].find_one()
print(doc.keys() if doc else "No doc")
if doc and '_id' in doc:
    print(f"_id: {doc['_id']} (type: {type(doc['_id'])})")
if doc and 'id' in doc:
    print(f"id: {doc['id']} (type: {type(doc['id'])})")
