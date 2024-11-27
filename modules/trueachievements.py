import os
import requests
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from flask import render_template
from typing import List, Dict, Any

class TrueAchievementsAPI:
    def __init__(self):
        self.base_url = 'https://www.trueachievements.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()

    def get_hq_image_url(self, thumb_url: str) -> str:
        if not thumb_url or '/api/placeholder/' in thumb_url:
            return '/api/placeholder/300/200'
            
        try:
            return thumb_url.replace('/thumbs/', '/xl/')
        except:
            return thumb_url

    def parse_numeric_value(self, text: str) -> int:
        try:
            return int(text.replace(',', '').replace('(', '').replace(')', '').strip())
        except:
            return 0

    def parse_ratio(self, text: str) -> tuple[int, int]:
        try:
            parts = text.strip().split(' of ')
            if len(parts) == 2:
                current = self.parse_numeric_value(parts[0])
                total = self.parse_numeric_value(parts[1])
                return current, total
            return 0, 0
        except:
            return 0, 0

    def fetch_games_list(self, username: str) -> tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        #Fetch games list and calculate statistics
        try:
            url = f'{self.base_url}/gamer/{username}/games'
            response = self.session.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 404:
                return [], self.get_empty_stats(), {}

            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            game_rows = soup.select('tr')
            games = []
            
            # Statistics tracking
            total_gamerscore = 0
            total_completion = 0.0
            completed_games = 0
            valid_games = 0
            monthly_achievements = {
                'Jan': 0, 'Feb': 0, 'Mar': 0, 'Apr': 0,
                'May': 0, 'Jun': 0, 'Jul': 0, 'Aug': 0,
                'Sep': 0, 'Oct': 0, 'Nov': 0, 'Dec': 0
            }
            
            for row in game_rows:
                try:
                    if not row.find('td'):
                        continue
                    
                    cells = row.find_all('td')
                    if len(cells) < 5:
                        continue

                    # Get title, image and URL
                    title_link = row.select_one('td.gamethumb a')
                    if not title_link or not title_link.find('img'):
                        continue
                        
                    # Get game URL from the title link
                    game_url = title_link.get('href', '')
                    if game_url and not game_url.startswith(('http://', 'https://')):
                        game_url = f'{self.base_url}{game_url}'
                        
                    img = title_link.find('img')
                    image_url = img.get('src', '')
                    if image_url and not image_url.startswith(('http://', 'https://')):
                        image_url = f'{self.base_url}{image_url}'

                    hq_image_url = self.get_hq_image_url(image_url)

                    # Parse achievements
                    achievements_current, achievements_total = self.parse_ratio(cells[2].text.strip())
                    
                    # Parse TA points
                    ta_current, ta_total = self.parse_ratio(cells[3].text.strip())
                    
                    # Parse gamerscore
                    gamerscore_current, gamerscore_total = self.parse_ratio(cells[4].text.strip())
                    
                    # Calculate completion percentage
                    completion = (ta_current / ta_total * 100) if ta_total > 0 else 0
                    
                    # Get last played date
                    last_played = None
                    try:
                        date_cell = row.select_one('td.date')
                        if date_cell:
                            last_played = date_cell.text.strip()
                    except:
                        pass

                    # Update statistics
                    total_gamerscore += gamerscore_current
                    if completion > 0:
                        total_completion += completion
                        valid_games += 1
                    if completion >= 100:
                        completed_games += 1
                    
                    game = {
                        'title': img.get('alt', '').strip(),
                        'image_url': hq_image_url,
                        'url': game_url,
                        'achievements': f"{achievements_current:,} of {achievements_total:,}",
                        'achievements_current': achievements_current,
                        'achievements_total': achievements_total,
                        'gamerscore': f"{gamerscore_current:,} of {gamerscore_total:,}",
                        'completion': completion,
                        'completion_display': f"{completion:.1f}%",
                        'ta_points': f"{ta_current:,} of {ta_total:,}",
                        'last_played': last_played
                    }
                            
                    games.append(game)
                    
                    # Update monthly achievements
                    if last_played:
                        try:
                            date = datetime.strptime(last_played, '%d %b %Y')
                            month = date.strftime('%b')
                            monthly_achievements[month] += achievements_current
                        except:
                            pass
                    
                except Exception as e:
                    print(f"Error processing game row: {str(e)}")
                    continue
            
            # Calculate statistics
            stats = {
                'total_games': len(games),
                'total_gamerscore': total_gamerscore,
                'average_completion': total_completion / valid_games if valid_games > 0 else 0,
                'completed_games': completed_games
            }

            # Sort games by last played date for recent section
            games.sort(key=lambda x: datetime.strptime(x['last_played'], '%d %b %Y') if x['last_played'] else datetime.min, reverse=True)
            
            # Prepare chart data
            chart_data = {
                'labels': list(monthly_achievements.keys()),
                'data': list(monthly_achievements.values())
            }
            
            return games, stats, chart_data
            
        except Exception as e:
            print(f"Error in fetch_games_list: {str(e)}")
            print(traceback.format_exc())
            return [], self.get_empty_stats(), {}

    def get_empty_stats(self) -> Dict[str, Any]:
        return {
            'total_games': 0,
            'total_gamerscore': 0,
            'average_completion': 0,
            'completed_games': 0
        }

def init_trueachievements_routes(app):
    ta_api = TrueAchievementsAPI()
    
    @app.route('/trueachievements')
    def achievements():
        try:
            username = os.getenv('TRUEACHIEVEMENTS_USERNAME')
            if not username:
                raise ValueError("TrueAchievements username not configured")
                
            games, stats, chart_data = ta_api.fetch_games_list(username)
            
            return render_template(
                'trueachievements.html',
                games=games,
                stats=stats,
                chart_data=chart_data,
                username=username
            )
            
        except Exception as e:
            print(f"Error rendering games page: {str(e)}")
            print(traceback.format_exc())
            return render_template(
                'trueachievements.html',
                error=str(e),
                games=[],
                stats=ta_api.get_empty_stats(),
                chart_data={'labels': [], 'data': []},
                username=os.getenv('TRUEACHIEVEMENTS_USERNAME')
            )