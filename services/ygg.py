import aiohttp
import logging
import asyncio
import xml.etree.ElementTree as ET
import re
from utils import check_season_episode

class YggService:
    def __init__(self, passkey=None, url="https://relay.ygg.gratis/torznab"):
        self.passkey = passkey
        self.base_url = url

    async def search(self, params):
        """
        Recherche sur le relay Torznab de YGG
        """
        logging.info(f"YGG Torznab Search: {params.get('q')}")

        async with aiohttp.ClientSession(trust_env=True) as session:
            try:
                async with session.get(self.base_url, params=params, timeout=20) as response:
                    if response.status == 200:
                        text = await response.text()
                        return self._parse_xml(text)
                    else:
                        logging.warning(f"YGG Relay Error {response.status}")
                        body = await response.text()
                        logging.warning(f"YGG Relay Body: {body[:200]}")
            except Exception as e:
                logging.error(f"YGG Relay Exception: {e}")
        return []

    def _parse_xml(self, xml_text):
        """Parse Torznab XML response from YGG relay"""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logging.error(f"YGG Relay XML Parse Error: {e}")
            return []

        # Torznab namespace
        ns = {'torznab': 'http://torznab.com/schemas/2015/feed'}

        items = root.findall('.//item')
        logging.info(f"YGG Relay found {len(items)} results")

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
            magnet_url = None

            for attr in item.findall('torznab:attr', ns):
                name = attr.get('name')
                value = attr.get('value')
                if name == 'infohash':
                    info_hash = value.lower() if value else None
                elif name == 'seeders':
                    seeders = int(value) if value else 0
                elif name == 'peers':
                    leechers = int(value) if value else 0
                elif name == 'magneturl':
                    magnet_url = value

            # Prioritize magnet link if found
            final_link = magnet_url or download_link
            
            # If we still don't have an info_hash but have a magnet, extract it
            if not info_hash and final_link and 'btih:' in final_link:
                hash_match = re.search(r'btih:([a-fA-F0-9]{40})', final_link, re.IGNORECASE)
                if hash_match:
                    info_hash = hash_match.group(1).lower()

            result = {
                "name": title,
                "size": int(size_text) if size_text else 0,
                "tracker_name": "YGG",
                "info_hash": info_hash,
                "magnet": final_link if final_link.startswith('magnet:') else None,
                "link": final_link,
                "source": "ygg",
                "seeders": seeders,
                "leechers": leechers
            }
            normalized.append(result)

        return normalized

    async def search_movie(self, title, year, original_title=None):
        """Recherche de films sur YGG (en français et anglais en parallèle)"""
        tasks = []
        
        # Titre français
        if title:
            q = f"{title} {year}".strip()
            tasks.append(self.search({"t": "movie", "q": q}))
        
        # Titre original
        if original_title and original_title != title:
            q = f"{original_title} {year}".strip()
            tasks.append(self.search({"t": "movie", "q": q}))
            
        if not tasks:
            return []
            
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        merged = self._merge_results(results_list)
        
        # Filtre de pertinence simple pour les films (Année)
        relevant = []
        for r in merged:
            if not year or str(year) in r.get('name', ''):
                relevant.append(r)
            else:
                relevant.append(r)
                
        return relevant

    async def search_series(self, title, season, episode, original_title=None):
        """Recherche de séries sur YGG (français/anglais + Episode/Pack en parallèle)"""
        tasks = []
        
        titles = [(title, "Français")]
        if original_title and original_title != title:
            titles.append((original_title, "Anglais"))
            
        for search_title, lang in titles:
            if not search_title: continue
            
            # 1. Recherche SxxExx
            if season is not None and episode is not None:
                q = f"{search_title} S{int(season):02d}E{int(episode):02d}"
                tasks.append(self.search({"t": "tvsearch", "q": q}))
            
            # 2. Recherche Pack Saison
            if season is not None:
                q = f"{search_title} S{int(season):02d}"
                tasks.append(self.search({"t": "tvsearch", "q": q}))
                
        if not tasks:
            return []
            
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        merged = self._merge_results(results_list)
        
        # Filtrage par saison/épisode
        relevant = [r for r in merged if check_season_episode(r.get('name', ''), season, episode)]
        
        return relevant

    def _merge_results(self, results_list):
        """Fusionne et déduplique les résultats des tâches parallèles"""
        all_results = []
        seen_hashes = set()
        
        for results in results_list:
            if isinstance(results, Exception) or not results:
                continue
            for r in results:
                ih = r.get('info_hash')
                if ih:
                    if ih not in seen_hashes:
                        all_results.append(r)
                        seen_hashes.add(ih)
                else:
                    # Si pas de hash (rare), on garde quand même
                    all_results.append(r)
        return all_results
