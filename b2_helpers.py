import requests
import hashlib
from flask import current_app

def upload_to_b2(file, filename):

    current_app.logger.info(f"Attempting to upload file: {filename}")
    
    # Get credentials from app config
    key_id = current_app.config['B2_KEY_ID']
    app_key = current_app.config['B2_APP_KEY']
    
    # 1. Get upload authorization
    auth_url = "https://api.backblazeb2.com/b2api/v2/b2_authorize_account"
    try:
        auth_response = requests.get(auth_url, auth=(key_id, app_key), timeout=30)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
    except Exception as e:
        current_app.logger.error(f"B2 authorization failed: {str(e)}")
        return None

    try:
        api_url = auth_data['apiUrl']
        auth_token = auth_data['authorizationToken']
        bucket_id = auth_data['allowed']['bucketId']
    except KeyError as e:
        current_app.logger.error(f"Missing key in B2 response: {str(e)}")
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
        current_app.logger.error(f"B2 upload URL failed: {str(e)}")
        return None

    # 3. Upload file
    try:
        file_data = file.read()
        content_type = file.content_type or 'application/octet-stream'
        
        upload_response = requests.post(
            upload_url,
            headers={
                "Authorization": upload_token,
                "X-Bz-File-Name": filename,
                "Content-Type": content_type,
                "X-Bz-Content-Sha1": hashlib.sha1(file_data).hexdigest()
            },
            data=file_data,
            timeout=60
        )
        upload_response.raise_for_status()
        
        # Return full public URL
        file_id = upload_response.json()['fileId']
        return f"{current_app.config['B2_BASE_URL']}{filename}"
    except Exception as e:
        current_app.logger.error(f"B2 upload failed: {str(e)}")
        return None