import aiohttp
import logging
import asyncio
import xml.etree.ElementTree as ET
from utils import check_season_episode

class LaCaleService:
    def __init__(self, passkey):
        self.passkey = passkey
        # Nouvel endpoint Torznab
        self.base_url = "https://la-cale.space/api/external/torznab"

    async def search(self, params):
        """
        Recherche générique sur LaCale via Torznab
        """
        if not self.passkey:
            return []

        # Ajouter l'apikey aux paramètres
        params['apikey'] = self.passkey
        
        logging.info(f"LaCale Torznab Search: {params.get('q') or 'ID search'}")

        async with aiohttp.ClientSession(trust_env=True) as session:
            try:
                async with session.get(self.base_url, params=params, timeout=20) as response:
                    if response.status == 200:
                        text = await response.text()
                        return self._parse_xml(text)
                    elif response.status in [401, 403]:
                        masked = self.passkey[:4] + "..." + self.passkey[-4:] if len(self.passkey) > 8 else "***"
                        logging.error(f"LaCale Unauthorized/Forbidden (401/403). Using key: {masked}. Please update your API KEY in /configure.")
                    else:
                        logging.warning(f"LaCale Error {response.status}")
            except Exception as e:
                logging.error(f"LaCale Exception: {e}")
        return []

    def _parse_xml(self, xml_text):
        """Parse Torznab XML response from LaCale"""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logging.error(f"LaCale XML Parse Error: {e}")
            return []

        # Torznab namespace
        ns = {'torznab': 'http://torznab.com/schemas/2015/feed'}

        items = root.findall('.//item')
        logging.info(f"LaCale found {len(items)} results")

        normalized = []
        for item in items:
            title = item.findtext('title', '')
            size_text = item.findtext('size', '0')
            
            # Extract basic links
            link = item.findtext('link', '')
            enclosure = item.find('enclosure')
            download_link = enclosure.get('url', '') if enclosure is not None else link

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

            normalized.append({
                "name": title,
                "size": int(size_text) if size_text else 0,
                "tracker_name": "LaCale",
                "info_hash": info_hash,
                "magnet": None, # Torznab usually doesn't give magnets directly
                "link": download_link,
                "source": "lacale",
                "seeders": seeders,
                "leechers": leechers
            })

        return normalized

    async def search_movie(self, title, year, tmdb_id=None, imdb_id=None):
        """Recherche de films sur LaCale par ID ou Titre"""
        params = {"t": "movie"}
        
        # Priorité aux IDs pour la précision
        if tmdb_id:
            params["tmdbid"] = tmdb_id
        elif imdb_id:
            # Enlever le 'tt' si présent
            params["imdbid"] = imdb_id.replace('tt', '')
        else:
            params["q"] = f"{title} {year}".strip()
            
        return await self.search(params)

    async def search_series(self, title, season, episode, tmdb_id=None, imdb_id=None):
        """Recherche de séries sur LaCale par ID et filtrage client"""
        params = {"t": "tvsearch"}
        
        # On cherche d'abord tout le contenu lié à l'ID
        if tmdb_id:
            params["tmdbid"] = tmdb_id
        elif imdb_id:
            params["imdbid"] = imdb_id.replace('tt', '')
        else:
            params["q"] = title

        if season is not None:
            params["season"] = season
        if episode is not None:
            params["ep"] = episode

        all_results = await self.search(params)
        
        # Filtrage précis par saison/épisode (SxxExx ou Pack)
        if season is not None:
            filtered = [r for r in all_results if check_season_episode(r.get('name', ''), season, episode)]
            logging.info(f"LaCale: {len(filtered)} results after season/episode filtering")
            return filtered
            
        return all_results
