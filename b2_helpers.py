import requests
import hashlib
from flask import current_app

def upload_to_b2(file, filename):
    try:
        # Log start of upload process
        current_app.logger.info(f"Starting B2 upload for: {filename}")
        
        # Get credentials
        key_id = current_app.config.get('B2_KEY_ID')
        app_key = current_app.config.get('B2_APP_KEY')
        bucket_name = current_app.config.get('B2_BUCKET_NAME')
        
        # Validate configuration
        if not key_id or not app_key or not bucket_name:
            error = "Missing Backblaze configuration"
            current_app.logger.error(error)
            return None

        # Log credentials (masked)
        current_app.logger.info(f"Using B2 Key ID: {key_id[:5]}...{key_id[-3:]}, Bucket: {bucket_name}")

        # 1. Get upload authorization
        auth_url = "https://s3.us-east-005.backblazeb2.com/b2api/v2/b2_authorize_account"
                    
        try:
            auth_response = requests.get(auth_url, auth=(key_id, app_key), timeout=30)
            auth_response.raise_for_status()
            auth_data = auth_response.json()
            current_app.logger.info("Auth successful")
        except Exception as e:
            error = f"Auth failed: {str(e)}"
            current_app.logger.error(error)
            current_app.logger.error(f"Auth response: {auth_response.text if 'auth_response' in locals() else 'No response'}")
            return None

        try:
            api_url = auth_data['apiUrl']
            auth_token = auth_data['authorizationToken']
            bucket_id = auth_data['allowed']['bucketId']
            download_url = auth_data['downloadUrl']
            current_app.logger.info(f"API URL: {api_url}, Bucket ID: {bucket_id}")
        except KeyError as e:
            error = f"Missing key in auth response: {str(e)}"
            current_app.logger.error(error)
            current_app.logger.error(f"Auth response: {auth_data}")
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
            current_app.logger.info(f"Upload URL: {upload_url}")
        except Exception as e:
            error = f"Upload URL failed: {str(e)}"
            current_app.logger.error(error)
            current_app.logger.error(f"Response: {upload_url_response.text}")
            return None

        # 3. Upload file
        try:
            file_data = file.read()
            content_type = file.content_type or 'application/octet-stream'
            file_hash = hashlib.sha1(file_data).hexdigest()
            current_app.logger.info(f"File size: {len(file_data)} bytes, SHA1: {file_hash}")
            
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
            current_app.logger.info(f"Upload response: {response_data}")
            
            # Construct public URL using download URL from auth
            public_url = f"{download_url}/file/{bucket_name}/{filename}"
            current_app.logger.info(f"Generated public URL: {public_url}")
            
            return public_url
        except Exception as e:
            error = f"Upload failed: {str(e)}"
            current_app.logger.error(error)
            current_app.logger.error(f"Response: {upload_response.text if 'upload_response' in locals() else 'No response'}")
            return None
            
    except Exception as e:
        current_app.logger.error(f"Unexpected error in upload_to_b2: {str(e)}")
        return None