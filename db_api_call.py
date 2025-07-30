import requests
import os
import json
import mimetypes
import re

API_BASE_URL = "https://laddr-api.azurewebsites.net"

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
    with open("token_response.json", "r") as f:
        data = json.load(f)
    try:
        response = requests.post(url, json=data, headers=headers, timeout=timeout)
        if response.status_code == 200:
            try:
                with open("token_response.json", "w") as f:
                    json.dump(response.json(), f)
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


def upsert_listing(property_data, user_id="4fce0a61-c632-4d4a-9f30-fb82bfdb6e59", country_id=2, state_id=3, city_id=6, property_type_id=6, postal_code_id=3, timeout=30, access_token=None):
    """
    Upserts a property listing using the exact payload format provided by the team.
    Sends data as _parts structure with field-value pairs.
    """
    with open("token_response.json", "r") as f:
        data = json.load(f)
    token_to_use = data.get("accessToken")
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
            agent_name = 'Foxtons ' + agent_email.split("@")[0].replace(".", " ").replace("_", " ").title()
        else:
            agent_name = "Agent Name"

    # PostalCodeText
    postal_code_text = property_data.get("further_details", {}).get("Postal Code", "")
    if not postal_code_text:
        address = property_data.get("address", "")
        address_parts = address.split(',')
        if len(address_parts) > 1:
            postal_code_text = address_parts[-1].strip()
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

    # StateId
    state_id = property_data.get("state_id", 3)
    try:
        state_id_int = int(state_id)
    except (ValueError, TypeError):
        state_id_int = 3
    if state_id_int == 0:
        state_id_int = 3

    # Build form data following the exact format from the successful request
    form_data = {
        "OutsideSpace": "0",
        "PostalCodeText": postal_code_text,
        "Bathrooms": str(_parse_int(property_data.get("rooms", {}).get("baths", 1))),
        "CityId": "6",
        "UserId": "b4e9560d-a60b-4736-ab5c-114e95b452ae",
        "PropertyCondition": property_data.get("further_details", {}).get("Property Condition", "New"),
        "Price": _parse_price(property_data.get("price", "")),
        "PropertyTypeId": property_data.get("property_type_id", ''),
        "StateId": property_data.get("state_id", ''),
        "UnitNumber": unit_number,
        "AgentName": agent_name,
        "TotalArea": str(_parse_area(property_data.get("further_details", {}).get("Total Sq Ft", ""))),
        "StreetAddress": _required_field(property_data.get("address", ""), "Property Address"),
        "CountryId": "2",
        "PostalCodeId": property_data.get("postal_code_id", ''),
        "EPCRating": _epc_rating_str(property_data.get("epc_rating", {})),
        "Bedrooms": str(_parse_int(property_data.get("rooms", {}).get("beds", 1))),
        "AgentEmail": _required_field(property_data.get("agent_email", ""), "agent@example.com"),
        "TubeLines": property_data.get("station_id", ""),
        "Description": _required_field(property_data.get("description", ""), "Property Description"),
        "EPCAccepted": "true",
        "ListingId": "0",
        "Tenure": property_data.get("further_details", {}).get("Tenure", "") or "",
        "Lease_Expires": property_data.get("further_details", {}).get("Lease Expires", "") or "",
        "Ground_Rent": property_data.get("further_details", {}).get("Ground Rent", "") or "",
        "Service_Charge": property_data.get("further_details", {}).get("Service Charge", "") or "",
        "Stamp_Duty": property_data.get("further_details", {}).get("Stamp Duty", "") or "",
        "Council_Tax": property_data.get("further_details", {}).get("Council Tax", "") or ""
    }

    print(form_data)

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


def get_states_by_country_id(country_id=2):
    """
    Fetches states by country ID from the Laddr API.

    Args:
        country_id (int or str): The ID of the country.
        access_token (str): Bearer token for authorization.
        base_url (str): Base URL for the API.

    Returns:
        tuple: (status_code, response_json or error dict)
    """
    import requests

    with open("token_response.json", "r") as f:
        data = json.load(f)
    token_to_use = data.get("accessToken")

    url = f"{API_BASE_URL}/api/State/GetByCountryId/{country_id}"
    headers = {
        "accept": "*/*",
        "Authorization": f"Bearer {token_to_use}"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            try:
                response_json = response.json()
                return response.status_code, response_json
            except Exception as e:
                print(f"Invalid JSON response: {str(e)}")
                return response.status_code, {"error": f"Invalid JSON response: {str(e)}"}
        elif response.status_code == 401:
            try:
                token_response = refresh_token()
                if token_response:
                    new_access_token = token_response.get("accessToken")
                    return get_states_by_country_id(country_id, new_access_token)
            except Exception as e:
                print(f"Error refreshing token: {str(e)}")
                return response.status_code, {"error": str(e)}
            print(f"Failed to fetch states: {response.text}")
            return response.status_code, {"error": response.text}
        else:
            print(f"Failed to fetch states: {response.text}")
            return response.status_code, {"error": response.text}
                
    except requests.RequestException as e:
        return None, {"error": str(e)}


def get_all_tube_lines():
    """
    Fetches all tube lines from the Laddr API.

    Args:
        access_token (str, optional): Bearer token for authorization. If None, will read from token_response.json.
        base_url (str, optional): Base URL for the API. If None, will use API_BASE_URL.

    Returns:
        tuple: (status_code, response_json or error dict)
    """

    with open("token_response.json", "r") as f:
        data = json.load(f)
    token_to_use = data.get("accessToken")

    url = f"{API_BASE_URL}/api/TubeLine/GetAll"
    headers = {
        "accept": "*/*",
        "Authorization": f"Bearer {token_to_use}"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            try:
                return response.status_code, response.json()
            except Exception as e:
                return response.status_code, {"error": f"Invalid JSON response: {str(e)}"}
        elif response.status_code == 401:
            # Try to refresh token if possible
            try:
                token_response = refresh_token()
                if token_response:
                    new_access_token = token_response.get("accessToken")
                    return get_all_tube_lines()
            except Exception as e:
                return response.status_code, {"error": f"Error refreshing token: {str(e)}"}
            return response.status_code, {"error": response.text}
        else:
            return response.status_code, {"error": response.text}
    except requests.RequestException as e:
        return None, {"error": str(e)}

def map_ids(self, property):

    if not self.connect_to_database():
        return
    
    # Load data
    if not self.load_property_data():
        return
    
    if not self.load_property_types():
        return
    
    if not self.load_postal_codes():
        return

    property_type_table = self.get_property_type_id()
    postal_code_table = self.get_postal_code_id()
    state_table = self.get_state_id()

    property_type_id_data = None
    postal_code_id_data = None
    state_id_data = None

    scrapped_description = property['description']
    scrapped_property_type = property['property_type']
    scrapped_further_details = property.get('further_details', {})

    postal_code_data_string = property['address'].split(',')[-1].strip().replace('0','').replace('1','').replace('2','').replace('3','').replace('4','').replace('5','').replace('6','').replace('7','').replace('8','').replace('9','')
    property['postal_code_text'] = postal_code_data_string

    for property_type_table_row in property_type_table:
        if property_type_table_row[1] == scrapped_property_type:
            property_type_id_data = property_type_table_row[0]
            property['property_type_id'] = property_type_id_data
            break

    for postal_code_table_row in postal_code_table:
        if postal_code_table_row[2] == postal_code_data_string:
            postal_code_id_data = postal_code_table_row[0]
            property['postal_code_id'] = postal_code_id_data
            break

    tenure = scrapped_further_details.get('Tenure', None)
    lease_expires = scrapped_further_details.get('Lease Expires', None)
    ground_rent = scrapped_further_details.get('Ground Rent', None)
    service_charge = scrapped_further_details.get('Service Charge', None)
    stamp_duty = scrapped_further_details.get('Stamp Duty', None)
    council_tax = scrapped_further_details.get('Council Tax', None)
    local_authority = scrapped_further_details.get('Local Authority', None)
    total_sq_ft = scrapped_further_details.get('Total Sq Ft', None)
    references = scrapped_further_details.get('References', None)

    property['tenure'] = tenure
    property['lease_expires'] = lease_expires
    property['ground_rent'] = ground_rent
    property['service_charge'] = service_charge
    property['stamp_duty'] = stamp_duty
    property['council_tax'] = council_tax
    property['total_sq_ft'] = total_sq_ft

    if local_authority:
        if '(' in local_authority:
            local_authority = local_authority.split(' ')[0]
        if 'The City of' in local_authority:
            local_authority = local_authority.split(' ')[3]

    for state_table_row in state_table:
        if state_table_row[1] == local_authority:
            state_id_data = state_table_row[0]
            property['state_id'] = state_id_data
            break

    return property
