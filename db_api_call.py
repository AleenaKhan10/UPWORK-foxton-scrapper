import requests
import os

API_BASE_URL = "https://laddr-api.azurewebsites.net"
REFRESH_TOKEN = "DhpVAuNh0vXi3HPaVRij480QUObdT5w3044ThKQAfDFtY8s/dVM402pbeT/EUTNcugAwZwZDKGlS+ynKkj7mFg=="
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ3YXFhckBsZXh1bXNvZnQuY29tIiwianRpIjoiOGU0MzIwNmYtYjdmMi00NTFiLTkxMTUtYWM2OWM0YzI0ZDhiIiwiaHR0cDovL3NjaGVtYXMueG1sc29hcC5vcmcvd3MvMjAwNS8wNS9pZGVudGl0eS9jbGFpbXMvbmFtZWlkZW50aWZpZXIiOiJiNGU5NTYwZC1hNjBiLTQ3MzYtYWI1Yy0xMTRlOTViNDUyYWUiLCJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9uYW1lIjoiV2FxYXIgS2hhbiIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IlVzZXIiLCJleHAiOjE3NTI3NzUyODIsImlzcyI6ImxhZGRyLmNvbSIsImF1ZCI6ImxhZGRyLmNvbSJ9.Z0fyPxwLGpt0ZR2i67e-3if5DZIfUos92TV_wdNmi7w"

def refresh_token(timeout=10):
    """
    Refresh the authentication token using the provided refresh token.

    Args:
        api_base_url (str): The base URL of the API (e.g., "https://example.com").
        refresh_token (str): The refresh token string.
        timeout (int): Timeout for the request in seconds.

    Returns:
        dict: A dictionary containing the new tokens if successful.
        None: If the refresh fails.
    """
    url = f"{API_BASE_URL.rstrip('/')}/api/Auth/refresh-token"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "refreshToken": REFRESH_TOKEN,
        "AccessToken": ACCESS_TOKEN
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=timeout)
        if response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                print(f"Token refresh succeeded but response is not valid JSON: {str(e)}")
                return None
        else:
            print(f"Token refresh failed with status {response.status_code}: {response.text}")
            return None
    except requests.RequestException as e:
        print(f"Token refresh request error: {str(e)}")
        return None

import mimetypes
import re

def upsert_listing(property_data, user_id="4fce0a61-c632-4d4a-9f30-fb82bfdb6e59", country_id=2, state_id=3, city_id=6, property_type_id=6, postal_code_id=3, timeout=30, access_token=None):
    """
    Upserts a property listing using the exact payload format provided by the team.
    Sends data as _parts structure with field-value pairs.
    """
    token_to_use = access_token if access_token else ACCESS_TOKEN
    url = f"{API_BASE_URL}/api/Listing/Upsert"
    headers = {
        "Authorization": f"Bearer {token_to_use}",
        "accept": "*/*"
    }

    def _required_field(val, fallback=""):
        if val is None:
            return fallback
        if isinstance(val, str) and val.strip() == "":
            return fallback
        return str(val)

    def _parse_price(price_str):
        if not price_str:
            return "0"
        price_cleaned = re.sub(r'[£,\s]', '', str(price_str))
        numbers = re.findall(r'\d+', price_cleaned)
        return numbers[0] if numbers else "0"

    def _parse_int(val):
        try:
            return int(val)
        except Exception:
            return 0

    def _parse_area(area_str):
        if not area_str:
            return 0
        match = re.search(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', str(area_str))
        if match:
            return int(float(match.group(1).replace(',', '')))
        return 0

    def _epc_rating_str(epc_rating):
        if isinstance(epc_rating, dict):
            current = epc_rating.get("current", "")
            potential = epc_rating.get("potential", "")
            if current:
                return current
            elif potential:
                return potential
            else:
                return "D"
        return str(epc_rating) if epc_rating else "D"

    def _tube_lines_str(stations):
        if not stations or not isinstance(stations, list):
            return "1,2,3"
        lines = []
        for s in stations:
            if isinstance(s, dict):
                info = s.get("station_info", "")
                if info and "line" in info.lower():
                    # Extract line numbers if available
                    line_nums = re.findall(r'\d+', info)
                    lines.extend(line_nums)
            elif isinstance(s, str):
                line_nums = re.findall(r'\d+', s)
                lines.extend(line_nums)
        return ",".join(lines[:3]) if lines else "1,2,3"

    # AgentName
    agent_name = property_data.get("further_details", {}).get("Agent Name", "")
    if not agent_name:
        agent_email = property_data.get("agent_email", "")
        if agent_email and "@" in agent_email:
            agent_name = agent_email.split("@")[0].replace(".", " ").replace("_", " ").title()
        else:
            agent_name = "Agent Name"

    # PostalCodeText
    postal_code_text = property_data.get("further_details", {}).get("Postal Code", "")
    if not postal_code_text:
        address = property_data.get("address", "")
        # Try to get the last part after the last comma, strip spaces, and check if it looks like a postcode
        if address and "," in address:
            possible_postcode = address.split(",")[-1].strip()
            # UK postcode regex, but fallback if not matched
            postcode_match = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b", possible_postcode, re.I)
            if postcode_match:
                postal_code_text = postcode_match.group(1).upper()
            else:
                # Try to find postcode anywhere in address as fallback
                postcode_match = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b", address, re.I)
                if postcode_match:
                    postal_code_text = postcode_match.group(1).upper()
                else:
                    postal_code_text = possible_postcode if possible_postcode else "SW1A 1AA"
        else:
            postcode_match = re.search(r"\b([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})\b", address, re.I)
            if postcode_match:
                postal_code_text = postcode_match.group(1).upper()
            else:
                postal_code_text = "SW1A 1AA"

    # UnitNumber
    unit_number = property_data.get("further_details", {}).get("Unit Number", "")
    if not unit_number:
        address = property_data.get("address", "")
        unit_match = None
        if address:
            unit_match = re.match(r"(?i)\s*(Flat|Apt|Apartment|Unit|Suite)?\s*([A-Za-z0-9\-]+)", address)
        if unit_match and unit_match.group(2):
            unit_number = unit_match.group(2)
        else:
            unit_number = "1"

    # Build form data following the exact format from the successful request
    form_data = {
        "OutsideSpace": "0",
        "PostalCodeText": postal_code_text,
        "Bathrooms": str(_parse_int(property_data.get("rooms", {}).get("baths", 1))),
        "CityId": "6",
        "UserId": "b4e9560d-a60b-4736-ab5c-114e95b452ae",
        "PropertyCondition": property_data.get("further_details", {}).get("Property Condition", "New"),
        "Price": _parse_price(property_data.get("price", "")),
        "PropertyTypeId": "6",
        "StateId": "3",
        "UnitNumber": unit_number,
        "AgentName": agent_name,
        "TotalArea": str(_parse_area(property_data.get("further_details", {}).get("Total Sq Ft", ""))),
        "StreetAddress": _required_field(property_data.get("address", ""), "Property Address"),
        "CountryId": "2",
        "PostalCodeId": "3",
        "EPCRating": _epc_rating_str(property_data.get("epc_rating", {})),
        "Bedrooms": str(_parse_int(property_data.get("rooms", {}).get("beds", 1))),
        "AgentEmail": _required_field(property_data.get("agent_email", ""), "agent@example.com"),
        "TubeLines": _tube_lines_str(property_data.get("nearest_stations", [])),
        "Description": _required_field(property_data.get("description", ""), "Property Description"),
        "EPCAccepted": "true",
        "ListingId": "0"
    }

    # Handle images as files for ListingMedias
    files = []
    images = property_data.get("images", [])
    
    for img in images:
        local_path = img.get("local_path")
        if local_path and os.path.isfile(local_path):
            try:
                filename = os.path.basename(local_path)
                mime_type, _ = mimetypes.guess_type(local_path)
                if not mime_type:
                    mime_type = "image/jpeg"
                f = open(local_path, "rb")
                files.append(("ListingMedias", (filename, f, mime_type)))
            except Exception as e:
                print(f"Error opening image {local_path}: {str(e)}")
                continue

    # If no images, add a placeholder (empty file)
    if not files:
        files.append(("ListingMedias", ("placeholder.jpg", b"", "image/jpeg")))

    try:
        response = requests.post(
            url,
            headers=headers,
            data=form_data,
            files=files,
            timeout=timeout
        )
        
        if response.status_code in (200, 201):
            try:
                print("response.json()", response.json())
                print("response.status_code", response.status_code)
                return response.status_code, response.json()
            except Exception as e:
                print(f"Upsert succeeded but response is not valid JSON: {str(e)}")
                return response.status_code, {"message": "Success but invalid JSON response"}
        elif response.status_code == 400:
            try:
                error_json = response.json()
                print(f"Upsert failed with validation error: {error_json}")
                return response.status_code, error_json
            except Exception:
                print(f"Upsert failed with status 400: {response.text}")
                return response.status_code, {"error": response.text}
        elif response.status_code == 401:
            try:
                token_response = refresh_token()
                if token_response:
                    new_access_token = token_response.get("accessToken")
                    return upsert_listing(property_data, user_id, country_id, state_id, city_id, property_type_id, postal_code_id, timeout, new_access_token)
            except Exception as e:
                print(f"Error refreshing token: {str(e)}")
                return response.status_code, {"error": str(e)}
            print(f"Upsert failed with status 401: {response.text}")
            return response.status_code, {"error": response.text}
        else:
            print(f"Upsert failed with status {response.status_code}: {response.text}")
            return response.status_code, {"error": response.text}
            
    except requests.RequestException as e:
        print(f"Upsert request error: {str(e)}")
        return None, {"error": str(e)}
    finally:
        # Ensure all files are closed
        for _, (fname, fobj, _) in files:
            try:
                fobj.close()
            except Exception:
                pass
