from pymongo import MongoClient
import datetime

# 1. Connect to your MongoDB Atlas cluster.
#    Replace <username>, <password>, and <cluster-url> with your actual connection details.
client = MongoClient("mongodb+srv://readonly_user:lucky0218@cluster0.lqm6b.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# 2. Select the database and the collection.
db = client["meteo"]
test_collection = db["test"]

# Define a function to query by Station and Date
def query_by_station_and_date(collection, station, date):
    """
    Query the collection for documents matching the specified Station and Date.
    
    Parameters:
    - collection: The MongoDB collection to query.
    - station: The station ID (integer).
    - date: The date to query (datetime object).
    
    Returns:
    - A list of documents matching the query.
    """
    query = {"Station": station, "Date": date}
    results = collection.find(query)
    return list(results)

def basic_read_test():
    # Example 1: Query for Station 58238 on January 1, 2024
    specific_station = 58238
    specific_date = datetime.datetime(2024, 1, 1)
    results = query_by_station_and_date(test_collection, specific_station, specific_date)
    print(f"\nFound {len(results)} documents for Station {specific_station} on {specific_date}:")
    for doc in results:
        print(doc)
# 3. Create a Python dictionary that mirrors your document structure.
#    - Station: an integer
#    - Date: stored as a Python datetime object (so MongoDB sees it as a Date)
#    - Avg: a float
#    - FDAvg: a float

def basic_insert_test():
    doc_to_insert = {
        "Station": 58349,
        "Date": datetime.datetime(2024, 1, 1),  #  Use Python's datetime to get an ISODate type in Mongo
        "Avg": 3.8,
        "FDAvg": 2.5
    }

    # 4. Insert the document into MongoDB.
    insert_result = test_collection.insert_one(doc_to_insert)

    # 5. Print the inserted ID to verify.
    print("Inserted document ID:", insert_result.inserted_id)

def main():
    basic_read_test()

if __name__ == "__main__":
    main()
