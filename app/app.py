from flask import Flask, json, render_template, request, json
from flask_cors import CORS
from pymongo import MongoClient
import datetime
import os
import sys
import serverless_wsgi

# Get the absolute path of the current file (app.py)
current_file = os.path.abspath(__file__)
# Get the directory containing app.py (ds)
current_dir = os.path.dirname(current_file)
# Get the parent directory (project)
parent_dir = os.path.dirname(current_dir)
# Add the parent directory to sys.path
sys.path.append(parent_dir)

# Import station_list from config.py
from app.config import station_list

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": os.environ.get("FRONTEND_URL")}})

# MongoDB connection string – replace the password/credentials as needed
MONGO_CONNECTION_STRING = os.environ.get("MONGO_CONNECTION_STRING")
client = MongoClient(MONGO_CONNECTION_STRING)
db = client["meteo"]
test_collection = db["test"]
temperature_collection = db["temp"]

# Netlify handler
def handler(event, context):
    return serverless_wsgi.handle_request(app, event, context)

def handle_api_error(e, message="Internal server error"):
    app.logger.error(f"Error: {str(e)}")
    return json.jsonify({
        "success": False,
        "error": message
    }), 500

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route("/", methods=["GET"])
def server():
    return render_template("server.html")

@app.route("/by_station", methods=["GET"])
def by_station():
    if request.method == "GET":
        selected_station = request.args.get("station")
        start_date = request.args.get("start")
        end_date = request.args.get("end")

        if not selected_station:
            return json.jsonify({"success": False, "error": "Station parameter is required"}), 400

        try:
            selected_station = int(selected_station)

            query = {"Station": selected_station}

            # Add date range filter if both start_date and end_date are provided
            if start_date or end_date:
                try:
                    if start_date:
                        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                        query["Date"] = {"$gte": start_date}
                    if end_date:
                        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                        if "Date" in query:
                            query["Date"]["$lte"] = end_date
                        else:
                            query["Date"] = {"$lte": end_date}
                except ValueError as e:
                    return json.jsonify({"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}), 400

            data = list(temperature_collection.find(query).sort("Date", -1))
            data.reverse()

            # Remove redundant results based on Station and Date
            unique_data = []
            seen = set()
            for doc in data:
                key = (doc["Station"], doc["Date"].strftime("%Y-%m-%d")) 
                if key not in seen:
                    seen.add(key)
                    unique_data.append(doc)

            if not unique_data:
                return json.jsonify({"success": False, "error": "No data found for the provided date range"}), 404

            # Prepare the response
            response = [{
                "Avg": doc["Avg"],
                "Date": doc["Date"].strftime("%Y-%m-%d"),
                "FDAvg": doc["FDAvg"],
                "Station": doc["Station"],
                "_id": str(doc["_id"]),
            } for doc in unique_data]

            return json.jsonify({"success": True, "data": response})

        except Exception as e:
            return json.jsonify({"success": False, "error": str(e)}), 500
    else:
        return json.jsonify({"success": False, "error": "Invalid request method"}), 405

@app.route("/by_date", methods=["GET"])
def by_date():
    if request.method == "GET":
        try:
            date_str = request.args.get("date")
            if not date_str:
                return json.jsonify({
                    "success": False,
                    "error": "Date parameter is required"
                }), 400

            try:
                chosen_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                next_day = chosen_date + datetime.timedelta(days=1)
            except ValueError:
                return json.jsonify({
                    "success": False,
                    "error": "Invalid date format (YYYY-MM-DD required)"
                }), 400

            data = list(temperature_collection.find({
                "Date": {"$gte": chosen_date, "$lt": next_day},
                "Station": {"$in": station_list}
            }))

            if not data:
                return json.jsonify({
                    "success": False,
                    "error": "No data found for this date"
                }), 404

            return json.jsonify({
                "success": True,
                "data": [{
                    "Avg": doc["Avg"],
                    "Date": doc["Date"].strftime("%Y-%m-%d"),
                    "FDAvg": doc["FDAvg"],
                    "Station": doc["Station"],
                    "_id": str(doc["_id"]),
                } for doc in data]
            })

        except Exception as e:
            return handle_api_error(e)
    else:
        return json.jsonify({
            "success": False,
            "error": "Invalid request method"
        }), 405

@app.route("/by_multiple_stations", methods=["GET"])
def by_multiple_stations():
    if request.method == "GET":
        stations = request.args.get("stations")
        start_date = request.args.get("start")
        end_date = request.args.get("end")
        table_data = {}

        if not stations:
            return json.jsonify({"success": False, "error": "Stations parameter is required"}), 400

        try:
            station_codes = [int(s) for s in stations.split(",") if s.strip()]

            query = {"Station": {"$in": station_codes}}

            if start_date or end_date:
                date_filter = {}
                try:
                    if start_date:
                        start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                        date_filter["$gte"] = start_date_obj
                    if end_date:
                        end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                        date_filter["$lte"] = end_date_obj
                    query["Date"] = date_filter
                except ValueError:
                    return json.jsonify({
                        "success": False,
                        "error": "Invalid date format. Use YYYY-MM-DD"
                    }), 400

            data = list(temperature_collection.find(query).sort("Date", -1))
            data.reverse() 

            if not data:
                return json.jsonify({"success": False, "error": "No data found for the provided criteria"}), 404

            # Remove duplicate records
            unique_data = []
            seen = set()
            for doc in data:
                key = (doc["Station"], doc["Date"].strftime("%Y-%m-%d"))
                if key not in seen:
                    seen.add(key)
                    unique_data.append(doc)

            for doc in unique_data:
                date_str = doc["Date"].strftime("%Y-%m-%d")
                station_code = str(doc["Station"])

                # Initialize date key if not present
                if date_str not in table_data:
                    table_data[date_str] = {}

                # Assign station data
                table_data[date_str][station_code] = {
                    "averageTemperature": doc["Avg"],
                    "fiveDayAverageTemperature": doc["FDAvg"]
                }

            table_data_array = [{"date": date, **stations} for date, stations in table_data.items()]

            return json.jsonify({"success": True, "data": table_data_array})

        except Exception as e:
            return json.jsonify({"success": False, "error": str(e)}), 500
    else:
        return json.jsonify({"success": False, "error": "Invalid request method"}), 405


@app.route("/advancedAnalysis", methods=["POST"])
def advanced_analysis():
    if request.method == "POST":
        try:
            data = request.get_json()
            if not data:
                return json.jsonify({
                    "success": False,
                    "error": "Invalid request body"
                }), 400

            stations = data.get('stations')
            date_str = data.get('date')

            if not stations or not isinstance(stations, list):
                return json.jsonify({
                    "success": False,
                    "error": "Invalid or missing stations list"
                }), 400

            if len(stations) < 1 or len(stations) > 3:
                return json.jsonify({
                    "success": False,
                    "error": "Please select 1-3 stations"
                }), 400

            if not date_str:
                return json.jsonify({
                    "success": False,
                    "error": "Date parameter is required"
                }), 400

            try:
                target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                next_day = target_date + datetime.timedelta(days=1)
            except ValueError:
                return json.jsonify({
                    "success": False,
                    "error": "Invalid date format (YYYY-MM-DD required)"
                }), 400

            try:
                station_codes = [int(code) for code in stations]
                invalid_stations = [code for code in station_codes if code not in station_list]
                if invalid_stations:
                    return json.jsonify({
                        "success": False,
                        "error": f"Invalid station codes: {invalid_stations}"
                    }), 400
            except ValueError:
                return json.jsonify({
                    "success": False,
                    "error": "Invalid station code format"
                }), 400

            query = {
                "Station": {"$in": station_codes},
                "Date": {"$gte": target_date, "$lt": next_day}
            }

            data = list(temperature_collection.find(query))

            if not data:
                return json.jsonify({
                    "success": False,
                    "error": "No data found for selected stations on this date"
                }), 404

            return json.jsonify({
                "success": True,
                "data": [{
                    "Avg": doc["Avg"],
                    "Station": doc["Station"],
                    "Date": doc["Date"].strftime("%Y-%m-%d")
                } for doc in data]
            })

        except Exception as e:
            return handle_api_error(e)
    else:
        return json.jsonify({
            "success": False,
            "error": "Invalid request method"
        }), 405
    
def main():
    app.run(debug=True)

if __name__ == "__main__":
    main()