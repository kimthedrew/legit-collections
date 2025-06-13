import requests
import hashlib
from flask import current_app
import logging

def upload_to_b2(file, filename):
    # Get credentials
    key_id = current_app.config.get('B2_KEY_ID')
    app_key = current_app.config.get('B2_APP_KEY')
    bucket_name = current_app.config.get('B2_BUCKET_NAME')
    base_url = current_app.config.get('B2_BASE_URL')
    
    # Validate configuration
    if not all([key_id, app_key, bucket_name, base_url]):
        current_app.logger.error("Missing Backblaze configuration")
        return None

    # 1. Get upload authorization
    auth_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
    try:
        auth_response = requests.get(auth_url, auth=(key_id, app_key), timeout=30)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        current_app.logger.info("Auth successful")
    except Exception as e:
        current_app.logger.error(f"Auth failed: {str(e)}")
        return None

    try:
        api_url = auth_data['apiUrl']
        auth_token = auth_data['authorizationToken']
        bucket_id = auth_data['allowed']['bucketId']
    except KeyError as e:
        current_app.logger.error(f"Missing key in auth response: {str(e)}")
        return None

    # 2. Get upload URL
    try:
        upload_url_response = requests.post(
            f"{api_url}/b2api/v2/b2_get_upload_url",
            headers={"Authorization": auth_token},
            json={"bucketId": bucket_id},
            timeout=30
        )
        upload_url_response.raise_for_status()
        upload_data = upload_url_response.json()
        upload_url = upload_data['uploadUrl']
        upload_token = upload_data['authorizationToken']
    except Exception as e:
        current_app.logger.error(f"Upload URL failed: {str(e)}")
        return None

    # 3. Upload file
    try:
        file_data = file.read()
        content_type = file.content_type or 'application/octet-stream'
        
        # Generate SHA1
        file_hash = hashlib.sha1(file_data).hexdigest()
        
        # Upload
        upload_response = requests.post(
            upload_url,
            headers={
                "Authorization": upload_token,
                "X-Bz-File-Name": filename,
                "Content-Type": content_type,
                "X-Bz-Content-Sha1": file_hash
            },
            data=file_data,
            timeout=60
        )
        upload_response.raise_for_status()
        response_data = upload_response.json()
        
        # Extract file ID and build URL
        file_id = response_data['fileId']
        file_name = response_data['fileName']
        
        # Construct URL using bucket name and file name
        # This is the most reliable way to get the public URL
        public_url = f"https://f002.backblazeb2.com/file/{bucket_name}/{file_name}"
        
        current_app.logger.info(f"Upload successful! Public URL: {public_url}")
        return public_url
    except Exception as e:
        current_app.logger.error(f"Upload failed: {str(e)}")
        return None