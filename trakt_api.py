import requests
from datetime import datetime
import os
from dotenv import load_dotenv

class TraktAPI:
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv('TRAKT_CLIENT_ID')
        self.client_secret = os.getenv('TRAKT_CLIENT_SECRET')
        self.tmdb_api_key = os.getenv('TMDB_API_KEY')
        self.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
        self.base_url = 'https://api.trakt.tv'
        self.tmdb_base_url = 'https://api.themoviedb.org/3'
        self.headers = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.client_id,
            'Accept': 'application/json'
        }
        self.access_token = os.getenv('TRAKT_ACCESS_TOKEN')
        if self.access_token:
            self.headers['Authorization'] = f'Bearer {self.access_token}'

    def authenticate(self):
        response = requests.post(
            f'{self.base_url}/oauth/device/code',
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'client_id': self.client_id
            }
        )
        if response.status_code != 200:
            raise Exception('Failed to get device code')
        
        device_code_data = response.json()
        print(f"Please go to {device_code_data['verification_url']} and enter code: {device_code_data['user_code']}")
        
        # Poll for the token
        token_response = requests.post(
            f'{self.base_url}/oauth/device/token',
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'code': device_code_data['device_code'],
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
        )
        
        if token_response.status_code == 200:
            token_data = token_response.json()
            self.access_token = token_data['access_token']
            self.headers['Authorization'] = f'Bearer {self.access_token}'
            print("Successfully authenticated!")
            return token_data
        else:
            raise Exception('Failed to get access token')

    def get_watched_shows(self):
        """Get complete list of watched shows with all available information"""
        response = requests.get(
            f'{self.base_url}/sync/watched/shows',
            headers=self.headers,
            params={'extended': 'full'}
        )
        
        if response.status_code != 200:
            print("API Response:", response.text)
            raise Exception('Failed to get watched shows')
        
        shows_data = response.json()
        shows_with_images = []
        
        for show in shows_data:
            if 'show' in show and 'ids' in show['show']:
                tmdb_id = show['show']['ids'].get('tmdb')
                if tmdb_id:
                    images = self.get_tmdb_images(tmdb_id)
                    if images:
                        show['show']['images'] = images
                shows_with_images.append(show)
                
                # Debug print
                print(f"\nDEBUG - Show: {show['show'].get('title')}")
                print(f"TMDb ID: {tmdb_id}")
                print(f"Images: {show['show'].get('images', {})}")
        
        return shows_with_images

    def get_watched_movies(self):
        """Get complete list of watched movies with all available information"""
        response = requests.get(
            f'{self.base_url}/sync/watched/movies',
            headers=self.headers,
            params={'extended': 'full,metadata'}
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get watched movies')
        return response.json()

    def get_watched_episodes(self):
        """Get complete list of watched episodes with all available information"""
        response = requests.get(
            f'{self.base_url}/sync/watched/episodes',
            headers=self.headers,
            params={'extended': 'full,metadata'}
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get watched episodes')
        return response.json()

    def get_watch_history(self, media_type=None, limit=20):
        """Get complete watch history with timestamps"""
        params = {'limit': limit, 'extended': 'full,metadata'}
        if media_type:
            params['type'] = media_type

        response = requests.get(
            f'{self.base_url}/sync/history',
            headers=self.headers,
            params=params
        )
        
        if response.status_code != 200:
            raise Exception('Failed to get watch history')
        return response.json()

    def get_tmdb_images(self, tmdb_id, media_type='tv'):
        """Get images from TMDb API"""
        if not self.tmdb_api_key or not tmdb_id:
            return None

        url = f'{self.tmdb_base_url}/{media_type}/{tmdb_id}'
        response = requests.get(url, params={'api_key': self.tmdb_api_key})
        
        if response.status_code == 200:
            data = response.json()
            return {
                'poster_url': f'https://image.tmdb.org/t/p/w500{data.get("poster_path")}' if data.get("poster_path") else None,
                'backdrop_url': f'https://image.tmdb.org/t/p/w1280{data.get("backdrop_path")}' if data.get("backdrop_path") else None
            }
        print(f"TMDb API error: {response.status_code} - {response.text}")
        return None