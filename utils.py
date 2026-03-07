import re
import unicodedata

def normalize_title(title):
    if not title:
        return ""
    # Remove accents
    title = unicodedata.normalize('NFD', title).encode('ascii', 'ignore').decode('utf-8')
    # Remove punctuation and special characters, replace with space
    title = re.sub(r'[^\w\s]', ' ', title)
    # lowercase and normalize spaces
    return " ".join(title.lower().split())

def check_title_match(torrent_name, title_fr, title_en, year=None, is_movie=False):
    """
    Vérifie si le titre français ou anglais est présent dans le nom du torrent.
    Pour les films, vérifie aussi l'année.
    """
    if not title_fr and not title_en:
        return True
        
    norm_torrent = normalize_title(torrent_name)
    norm_fr = normalize_title(title_fr)
    norm_en = normalize_title(title_en)
    
    title_match = False
    
    if norm_fr:
        pattern_fr = r'\b' + re.escape(norm_fr) + r'\b'
        if re.search(pattern_fr, norm_torrent):
            title_match = True
            
    if not title_match and norm_en:
        pattern_en = r'\b' + re.escape(norm_en) + r'\b'
        if re.search(pattern_en, norm_torrent):
            title_match = True
            
    if not title_match:
        if norm_fr and norm_fr in norm_torrent:
            title_match = True
        elif norm_en and norm_en in norm_torrent:
            title_match = True
            
    if not title_match:
        return False
        
    if is_movie and year:
        try:
            y = int(year)
            if str(y) not in norm_torrent and str(y-1) not in norm_torrent and str(y+1) not in norm_torrent:
                return False
        except ValueError:
            if str(year) not in norm_torrent:
                return False
                
    return True

def format_size(size_bytes):
    """Formate une taille en octets vers une chaine lisible (Go, Mo)"""
    try:
        size = float(size_bytes)
    except (ValueError, TypeError):
        return "0 B"

    if size >= 1024**3:
        return f"{size / (1024**3):.2f} Go"
    elif size >= 1024**2:
        return f"{size / (1024**2):.2f} Mo"
    else:
        return f"{size / 1024:.2f} Ko"

def parse_torrent_name(name):
    """Analyse le nom du torrent pour extraire qualité et langue"""
    name_upper = name.upper()
    
    # Qualité
    quality = ""
    if "2160P" in name_upper or "4K" in name_upper:
        quality = "4K"
    elif "1080P" in name_upper:
        quality = "1080p"
    elif "720P" in name_upper:
        quality = "720p"
    elif "480P" in name_upper or "SD" in name_upper:
        quality = "SD"
        
    # Codec / HDR
    extras = []
    if "HDR" in name_upper: extras.append("HDR")
    if "DV" in name_upper or "DOLBY VISION" in name_upper: extras.append("DV")
    if "X265" in name_upper or "HEVC" in name_upper: extras.append("x265")
    
    # Langues
    langs = []
    
    # Priorité aux Multi et VFF
    if "MULTI" in name_upper:
        langs.append("🇫🇷+🇺🇸 MULTI")
    elif "TRUEFRENCH" in name_upper or "VFF" in name_upper:
        langs.append("🇫🇷 VFF")
    elif "FRENCH" in name_upper or "VF" in name_upper:
        langs.append("🇫🇷 VF")
    elif "VOSTFR" in name_upper or "SUBFRENCH" in name_upper:
        langs.append("🇫🇷🇯🇵 VOSTFR")
        
    # Formatage final
    title_parts = []
    if quality: title_parts.append(f"📺 {quality}")
    if extras: title_parts.append(f"🎞️ {' '.join(extras)}")
    if langs: title_parts.append(f"{' '.join(langs)}")
    
    return " | ".join(title_parts)

def check_season_episode(name, target_season, target_episode):
    """
    Vérifie si le torrent correspond à la saison/épisode demandé.
    Retourne True si c'est bon (match exact ou pack saison).
    Retourne False si c'est un autre épisode/saison.
    """
    if target_season is None:
        return True
        
    name_upper = name.upper()
    
    # Extraction SxxExx
    # Regex améliorée pour capturer les ranges d'épisodes (ex: S05E02-E03 ou S05E02E03)
    se_pattern = re.compile(r'(?:S|SAISON|SEASON)[ ._-]?(\d{1,2})(?:[ ._-]?E(\d{1,2}))(?:[ ._-]?E?(\d{1,2}))?', re.IGNORECASE)
    matches = se_pattern.findall(name_upper)
    
    # Si aucun pattern Sxx trouvé, on essaie 1x01
    if not matches:
        x_pattern = re.compile(r'(\d{1,2})x(\d{1,2})', re.IGNORECASE)
        matches = [(m[0], m[1], None) for m in x_pattern.findall(name_upper)]
        
    # Si toujours rien, on cherche juste le pattern Saison sans épisode (Pack Saison)
    if not matches:
        s_only_pattern = re.compile(r'(?:S|SAISON|SEASON)[ ._-]?(\d{1,2})', re.IGNORECASE)
        matches = [(m, None, None) for m in s_only_pattern.findall(name_upper)]

    if not matches:
        return False # Pour une série, si on ne trouve aucune info de saison/épisode, on rejette

    for s, e_start, e_end in matches:
        try:
            season = int(s)
            if season != target_season:
                continue
                
            # Si pas d'épisode dans le nom (Pack Saison) -> OK
            if e_start is None:
                return True
                
            start = int(e_start)
            end = int(e_end) if e_end else start
            
            # Vérification de l'épisode (dans le range)
            if start <= target_episode <= end:
                return True
                
        except ValueError:
            continue
            
    return False

