import aiohttp
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from utils import check_season_episode

class Torr9Service:
    def __init__(self, passkey):
        self.passkey = passkey
        self.base_url = "https://api.torr9.xyz/api/v1/torznab"

    async def search(self, params):
        if not self.passkey:
            return []

        params['apikey'] = self.passkey
        
        # Log request (masking passkey)
        log_params = params.copy()
        log_params['apikey'] = '***PASSKEY***'
        logging.info(f"Torr9 Search: {self.base_url}?{urllib.parse.urlencode(log_params)}")

        async with aiohttp.ClientSession(trust_env=True) as session:
            try:
                async with session.get(self.base_url, params=params, timeout=20) as response:
                    if response.status == 200:
                        text = await response.text()
                        return self._parse_xml(text)
                    else:
                        logging.warning(f"Torr9 Error {response.status}")
                        body = await response.text()
                        logging.warning(f"Torr9 Body: {body[:200]}")
            except Exception as e:
                logging.error(f"Torr9 Exception: {e}")
        return []

    def _parse_xml(self, xml_text):
        """Parse Torznab XML response"""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logging.error(f"Torr9 XML Parse Error: {e}")
            return []

        # Torznab namespace
        ns = {'torznab': 'http://torznab.com/schemas/2015/feed'}

        items = root.findall('.//item')
        logging.info(f"Torr9 found {len(items)} results")

        normalized = []
        for item in items:
            title = item.findtext('title', '')
            guid = item.findtext('guid', '')
            size_text = item.findtext('size', '0')

            # Enclosure (download link)
            enclosure = item.find('enclosure')
            download_link = enclosure.get('url', '') if enclosure is not None else ''

            # Torznab attributes
            info_hash = None
            seeders = 0
            leechers = 0

            for attr in item.findall('torznab:attr', ns):
                name = attr.get('name')
                value = attr.get('value')
                if name == 'infohash':
                    info_hash = value.lower() if value else None
                elif name == 'seeders':
                    seeders = int(value) if value else 0
                elif name == 'peers':
                    leechers = int(value) if value else 0

            # Fallback to guid as hash
            if not info_hash:
                info_hash = guid.lower() if guid else None

            result = {
                "name": title,
                "size": int(size_text) if size_text else 0,
                "tracker_name": "Torr9",
                "info_hash": info_hash,
                "magnet": None,
                "link": download_link,
                "source": "torr9",
                "seeders": seeders,
                "leechers": leechers
            }
            normalized.append(result)

        return normalized

    async def search_movie(self, title, year, imdb_id=None, tmdb_id=None):
        params = {"t": "movie"}
        if imdb_id:
            if not str(imdb_id).startswith('tt'):
                imdb_id = f"tt{imdb_id}"
            params["imdbid"] = imdb_id
        elif tmdb_id:
            params["tmdbid"] = tmdb_id
        else:
            params["q"] = f"{title} {year}"
            
        return await self.search(params)

    async def search_series(self, title, season, episode, imdb_id=None, tmdb_id=None):
        params = {"t": "tvsearch"}
        if imdb_id:
            if not str(imdb_id).startswith('tt'):
                imdb_id = f"tt{imdb_id}"
            params["imdbid"] = imdb_id
        elif tmdb_id:
            params["tmdbid"] = tmdb_id
        else:
            params["q"] = title
            
        # Torznab filters for season/episode
        if season is not None:
            params["season"] = season
        if episode is not None:
            params["episode"] = episode
            
        return await self.search(params)
