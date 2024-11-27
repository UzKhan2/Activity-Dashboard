import os
import requests
import traceback
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime, timedelta
from flask import render_template, jsonify

class GitHubAPI:
    def __init__(self):
        self.base_url = 'https://api.github.com'
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {os.getenv("GITHUB_TOKEN")}',
            'User-Agent': 'GitHub-Activity-Tracker'
        }

    def fetch_user_activity(self, username: str) -> List[Dict[str, Any]]:
        try:
            url = f'{self.base_url}/users/{username}/events/public'
            response = self._make_request(url)
            return self._format_activities(response)
        except Exception as e:
            print(f"Error fetching GitHub activity: {str(e)}")
            return []

    def fetch_user_stats(self, username: str) -> Dict[str, Any]:
        try:
            # Fetch user repositories
            repos = self._make_request(f'{self.base_url}/users/{username}/repos')
            
            # Calculate total commits
            total_commits = 0
            total_prs = 0
            total_issues = 0
            
            for repo in repos:
                # Fetch commit stats for each repo
                since = (datetime.now() - timedelta(days=30)).isoformat()
                commits = self._make_request(
                    f'{self.base_url}/repos/{repo["full_name"]}/commits',
                    params={'since': since}
                )
                total_commits += len(commits)
                
                # Fetch PR stats
                prs = self._make_request(f'{self.base_url}/repos/{repo["full_name"]}/pulls?state=all')
                total_prs += len(prs)
                
                # Fetch issue stats
                issues = self._make_request(f'{self.base_url}/repos/{repo["full_name"]}/issues?state=all')
                total_issues += len(issues)

            return {
                'total_commits': total_commits,
                'total_repos': len(repos),
                'total_prs': total_prs,
                'total_issues': total_issues
            }
        except Exception as e:
            print(f"Error fetching user stats: {str(e)}")
            return {}

    def fetch_user_repos(self, username: str) -> List[Dict[str, Any]]:
        try:
            repos = self._make_request(f'{self.base_url}/users/{username}/repos?sort=updated')
            return [{
                'name': repo['name'],
                'description': repo['description'],
                'stars': repo['stargazers_count'],
                'forks': repo['forks_count'],
                'watchers': repo['watchers_count'],
                'language': repo['language'],
                'url': repo['html_url']
            } for repo in repos[:10]]  # Amount of repos returned
        except Exception as e:
            print(f"Error fetching repositories: {str(e)}")
            return []

    def fetch_user_commits(self, username: str) -> List[Dict[str, Any]]:
        #Fetch user's recent commits across all repositories
        try:
            events = self._make_request(
                f'{self.base_url}/users/{username}/events/public'
            )
            
            commits = []
            for event in events:
                if event['type'] == 'PushEvent':
                    for commit in event['payload'].get('commits', []):
                        commits.append({
                            'repo': event['repo']['name'],
                            'message': commit['message'],
                            'date': event['created_at'],
                            'url': f"https://github.com/{event['repo']['name']}/commit/{commit['sha']}"
                        })
            
            return commits[:20]  # Return only the 20 most recent commits
        except Exception as e:
            print(f"Error fetching commits: {str(e)}")
            return []

    def fetch_activity_chart_data(self, username: str) -> Dict[str, Any]:
        #Fetch data for the activity chart
        try:
            # Get events from the last 30 days
            events = self._make_request(
                f'{self.base_url}/users/{username}/events/public'
            )
            
            # Group events by day
            monthly_activity = defaultdict(int)
            for event in events:
                date = datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                day = date.strftime('%Y-%m-%d')
                monthly_activity[day] += 1
            
            # Format for the chart
            sorted_days = sorted(monthly_activity.keys())
            return {
                'months': [
                    {'month': day, 'count': monthly_activity[day]}
                    for day in sorted_days
                ]
            }
        except Exception as e:
            print(f"Error fetching activity chart data: {str(e)}")
            return {'months': []}

    def _make_request(self, url: str, params: Dict = None) -> Any:
        #GitHub API request with error handling
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 401:
                raise Exception("Authentication error")
            if response.status_code == 403:
                raise Exception("Rate limit exceeded")
            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code}")
                
            return response.json()
            
        except Exception as e:
            print(f"Request error for {url}: {str(e)}")
            raise

    def _format_activities(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        #Format raw GitHub events into structured activity data
        activities = []
        for event in events:
            try:
                activity = {
                    'type': event['type'],
                    'date': event['created_at'],
                    'repo': event['repo']['name'],
                    'url': f"https://github.com/{event['repo']['name']}"
                }
                
                if event['type'] == 'PushEvent' and 'payload' in event:
                    commits = event['payload'].get('commits', [])
                    activity['commits'] = [{
                        'message': c['message'],
                        'url': f"{activity['url']}/commit/{c['sha']}"
                    } for c in commits]
                elif event['type'] == 'CreateEvent' and 'payload' in event:
                    activity['ref_type'] = event['payload'].get('ref_type')
                    activity['ref'] = event['payload'].get('ref')
                elif event['type'] == 'IssuesEvent' and 'payload' in event:
                    activity['action'] = event['payload'].get('action')
                    if 'issue' in event['payload']:
                        activity['issue'] = {
                            'title': event['payload']['issue']['title'],
                            'url': event['payload']['issue']['html_url']
                        }
                elif event['type'] == 'WatchEvent' and 'payload' in event:
                    activity['action'] = event['payload'].get('action')
                elif event['type'] == 'PublicEvent':
                    activity['action'] = 'published'
                
                activities.append(activity)
                
            except Exception as e:
                print(f"Error processing event: {str(e)}")
                continue
                
        return activities

def init_github_routes(app):
    github_api = GitHubAPI()
    
    @app.route('/github')
    def github():
        try:
            github_username = os.getenv('GITHUB_USERNAME')
            if not github_username:
                raise ValueError("GitHub username not configured")
            
            activities = github_api.fetch_user_activity(github_username)
            return render_template('github.html', activities=activities)
            
        except Exception as e:
            error_msg = f"Error fetching GitHub activities: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            return render_template('github.html', activities=[], error=error_msg)

    @app.route('/api/github/stats')
    def github_stats():
        try:
            github_username = os.getenv('GITHUB_USERNAME')
            stats = github_api.fetch_user_stats(github_username)
            return jsonify(stats)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/github/commits')
    def github_commits():
        try:
            github_username = os.getenv('GITHUB_USERNAME')
            commits = github_api.fetch_user_commits(github_username)
            return jsonify(commits)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/github/repos')
    def github_repos():
        try:
            github_username = os.getenv('GITHUB_USERNAME')
            repos = github_api.fetch_user_repos(github_username)
            return jsonify(repos)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/github/activity')
    def github_activity():
        try:
            github_username = os.getenv('GITHUB_USERNAME')
            activity_data = github_api.fetch_activity_chart_data(github_username)
            return jsonify(activity_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500