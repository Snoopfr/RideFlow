import streamlit as st
import sys
import traceback

# Test des imports critiques
missing_packages = []

try:
    import gpxpy
except ImportError:
    missing_packages.append("gpxpy")

try:
    import openmeteo_requests
except ImportError:
    missing_packages.append("openmeteo-requests")

try:
    import requests_cache
except ImportError:
    missing_packages.append("requests-cache")

try:
    from retry_requests import retry
except ImportError:
    missing_packages.append("retry-requests")

try:
    import numpy as np
except ImportError:
    missing_packages.append("numpy")

try:
    import pandas as pd
except ImportError:
    missing_packages.append("pandas")

try:
    import folium
except ImportError:
    missing_packages.append("folium")

try:
    from streamlit_folium import folium_static
except ImportError:
    missing_packages.append("streamlit-folium")

try:
    from geopy.distance import geodesic
except ImportError:
    missing_packages.append("geopy")

try:
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError:
    missing_packages.append("plotly")

import math
from datetime import datetime, timedelta
import json
import pytz

# Configuration de la page
st.set_page_config(
    page_title="🚴 Optimiseur de Parcours Cycliste",
    page_icon="🌪️",
    layout="wide"
)

# Vérification des dépendances
if missing_packages:
    st.error(f"⚠️ Packages manquants: {', '.join(missing_packages)}")
    st.code(f"pip install {' '.join(missing_packages)}")
    st.markdown("### Installation recommandée :")
    st.code("pip install openmeteo-requests requests-cache retry-requests numpy pandas gpxpy folium streamlit-folium geopy plotly pytz")
    st.stop()

class WindOptimizer:
    def __init__(self):
        # Setup Open-Meteo API client avec cache et retry
        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        self.openmeteo = openmeteo_requests.Client(session=retry_session)
        
        # Fuseau horaire France
        self.timezone = pytz.timezone('Europe/Paris')
        
        # Limite gratuite Open-Meteo : 7 jours de prévisions
        self.max_forecast_days = 7
        
        self.gpx_data = None
        self.weather_data = None
        
    def get_forecast_date_limits(self):
        """Retourne les dates limites pour les prévisions gratuites"""
        now = datetime.now(self.timezone)
        today = now.date()
        max_date = today + timedelta(days=self.max_forecast_days)
        return today, max_date
        
    def parse_gpx(self, gpx_file):
        """Parse le fichier GPX et extrait les coordonnées"""
        try:
            gpx = gpxpy.parse(gpx_file)
            points = []
            
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        points.append({
                            'lat': point.latitude,
                            'lon': point.longitude,
                            'elevation': point.elevation if point.elevation else 0
                        })
            
            return points
        except Exception as e:
            st.error(f"Erreur lors du parsing GPX: {str(e)}")
            return None
    
    def get_gpx_center_and_bounds(self, points):
        """Calcule le centre et les limites de la trace GPS"""
        if not points:
            return None, None
            
        lats = [p['lat'] for p in points]
        lons = [p['lon'] for p in points]
        
        center = {
            'lat': np.mean(lats),
            'lon': np.mean(lons)
        }
        
        bounds = {
            'north': max(lats),
            'south': min(lats),
            'east': max(lons),
            'west': min(lons)
        }
        
        return center, bounds
    
    def calculate_distance_and_bearing(self, points):
        """Calcule les distances et directions entre les points"""
        segments = []
        total_distance = 0
        
        for i in range(len(points) - 1):
            p1 = (points[i]['lat'], points[i]['lon'])
            p2 = (points[i+1]['lat'], points[i+1]['lon'])
            
            # Distance en mètres
            distance = geodesic(p1, p2).meters
            total_distance += distance
            
            # Direction (bearing) en degrés
            bearing = self.calculate_bearing(p1, p2)
            
            segments.append({
                'start_lat': points[i]['lat'],
                'start_lon': points[i]['lon'],
                'end_lat': points[i+1]['lat'],
                'end_lon': points[i+1]['lon'],
                'distance': distance,
                'bearing': bearing,
                'cumulative_distance': total_distance
            })
        
        return segments, total_distance
    
    def calculate_bearing(self, point1, point2):
        """Calcule la direction entre deux points GPS"""
        lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
        lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])
        
        dlon = lon2 - lon1
        
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        
        bearing = math.atan2(x, y)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360
        
        return bearing
    
    def get_weather_data(self, center_coords, start_datetime=None):
        """Récupère les données météo d'Open-Meteo pour les coordonnées centrales"""
        try:
            lat, lon = center_coords['lat'], center_coords['lon']
            
            # Affichage automatique des coordonnées envoyées
            st.info(f"📍 Envoi automatique des coordonnées GPS centrales à Open-Meteo:\n"
                   f"Latitude: {lat:.6f}°, Longitude: {lon:.6f}°")
            
            url = "https://api.open-meteo.com/v1/forecast"
            
            # Paramètres de base pour Open-Meteo
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": [
                    "temperature_2m", 
                    "wind_speed_10m", 
                    "wind_speed_80m", 
                    "wind_speed_120m",
                    "wind_direction_10m", 
                    "wind_direction_80m", 
                    "wind_direction_120m",
                    "wind_gusts_10m",
                    "precipitation",
                    "precipitation_probability"
                ],
                "timezone": "Europe/Paris"  # Fuseau horaire France
            }
            
            # Gestion des dates avec limites API
            today, max_date = self.get_forecast_date_limits()
            
            if start_datetime:
                target_date = start_datetime.date() if isinstance(start_datetime, datetime) else start_datetime
                
                if target_date < today:
                    # Date dans le passé - utiliser l'API historique
                    url = "https://archive-api.open-meteo.com/v1/archive"
                    params["start_date"] = target_date.strftime("%Y-%m-%d")
                    params["end_date"] = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    st.info(f"📅 Utilisation des données historiques pour {target_date}")
                    
                elif target_date > max_date:
                    # Date trop loin dans le futur
                    st.warning(f"⚠️ Date trop éloignée. Limitation à {self.max_forecast_days} jours maximum.")
                    st.warning(f"Utilisation des prévisions jusqu'au {max_date}")
                    params["start_date"] = today.strftime("%Y-%m-%d")
                    params["end_date"] = max_date.strftime("%Y-%m-%d")
                    
                else:
                    # Date dans la plage de prévision gratuite
                    params["start_date"] = target_date.strftime("%Y-%m-%d")
                    params["end_date"] = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    st.success(f"✅ Prévisions disponibles pour {target_date}")
            else:
                # Pas de date spécifique - prendre les prochains jours disponibles
                params["forecast_days"] = self.max_forecast_days
                st.info(f"📊 Récupération des prévisions pour les {self.max_forecast_days} prochains jours")
            
            # Affichage de l'URL et des paramètres envoyés
            with st.expander("🔍 Détails de la requête Open-Meteo"):
                st.write(f"**URL:** {url}")
                st.write("**Paramètres envoyés:**")
                st.json(params)
            
            responses = self.openmeteo.weather_api(url, params=params)
            response = responses[0]
            
            # Traitement des données horaires
            hourly = response.Hourly()
            
            # Vérification que nous avons des données
            if hourly is None:
                st.error("Aucune donnée horaire disponible")
                return None
            
            # Extraction des variables (ordre important !)
            try:
                hourly_data = {
                    "date": pd.date_range(
                        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                        freq=pd.Timedelta(seconds=hourly.Interval()),
                        inclusive="left"
                    )
                }
                
                # Conversion en heure locale française
                hourly_data["date"] = hourly_data["date"].tz_convert('Europe/Paris')
                
                # Mapping des variables dans l'ordre des paramètres
                variables_map = [
                    "temperature_2m",
                    "wind_speed_10m", 
                    "wind_speed_80m", 
                    "wind_speed_120m",
                    "wind_direction_10m", 
                    "wind_direction_80m", 
                    "wind_direction_120m",
                    "wind_gusts_10m",
                    "precipitation",
                    "precipitation_probability"
                ]
                
                for i, var_name in enumerate(variables_map):
                    try:
                        hourly_data[var_name] = hourly.Variables(i).ValuesAsNumpy()
                    except Exception as e:
                        st.warning(f"Variable {var_name} non disponible: {e}")
                        # Valeur par défaut
                        hourly_data[var_name] = np.zeros(len(hourly_data["date"]))
                
                df = pd.DataFrame(hourly_data)
                
                # Affichage des coordonnées réellement utilisées par Open-Meteo
                actual_coords = {'lat': response.Latitude(), 'lon': response.Longitude()}
                coord_diff = {
                    'lat_diff': abs(actual_coords['lat'] - center_coords['lat']),
                    'lon_diff': abs(actual_coords['lon'] - center_coords['lon'])
                }
                
                st.success(f"✅ Coordonnées traitées par Open-Meteo:\n"
                          f"Latitude: {actual_coords['lat']:.6f}° (écart: {coord_diff['lat_diff']:.6f}°)\n"
                          f"Longitude: {actual_coords['lon']:.6f}° (écart: {coord_diff['lon_diff']:.6f}°)")
                
                return {
                    'center_coordinates': center_coords,
                    'actual_coordinates': actual_coords,
                    'elevation': response.Elevation(),
                    'timezone': response.Timezone().decode('utf-8'),
                    'hourly_data': df,
                    'data_points': len(df)
                }
                
            except Exception as e:
                st.error(f"Erreur lors du traitement des données horaires: {e}")
                return None
            
        except Exception as e:
            st.error(f"Erreur API météo Open-Meteo: {str(e)}")
            return None
    
    def analyze_wind_impact_temporal(self, segments, weather_data, avg_speed_kmh, start_time=None):
        """Analyse l'impact du vent sur chaque segment avec données temporelles"""
        if start_time is None:
            start_time = datetime.now(self.timezone)
        elif start_time.tzinfo is None:
            start_time = self.timezone.localize(start_time)
            
        analyzed_segments = []
        hourly_df = weather_data['hourly_data']
        
        current_time = start_time
        cumulative_distance = 0
        
        for segment in segments:
            # Calcul du temps pour parcourir ce segment
            segment_time_hours = (segment['distance'] / 1000) / avg_speed_kmh
            
            # Trouve les données météo pour ce moment
            closest_weather = self.get_closest_weather_data(hourly_df, current_time)
            
            if closest_weather is not None:
                wind_speed = closest_weather['wind_speed_10m']  # km/h
                wind_direction = closest_weather['wind_direction_10m']
                
                # Angle entre la direction du cycliste et du vent
                wind_angle = abs(segment['bearing'] - wind_direction)
                if wind_angle > 180:
                    wind_angle = 360 - wind_angle
                
                # Classification du vent
                if wind_angle <= 45:  # Vent de face
                    wind_type = "face"
                    impact = -wind_speed * math.cos(math.radians(wind_angle))
                elif wind_angle >= 135:  # Vent de dos
                    wind_type = "dos"  
                    impact = wind_speed * math.cos(math.radians(180 - wind_angle))
                else:  # Vent latéral
                    wind_type = "lateral"
                    impact = 0
                
                analyzed_segments.append({
                    **segment,
                    'wind_angle': wind_angle,
                    'wind_type': wind_type,
                    'wind_impact': impact,
                    'wind_speed': wind_speed,
                    'wind_direction': wind_direction,
                    'time': current_time.strftime("%H:%M"),
                    'temperature': closest_weather.get('temperature_2m', 0),
                    'precipitation': closest_weather.get('precipitation', 0),
                    'precipitation_probability': closest_weather.get('precipitation_probability', 0)
                })
            
            # Avance le temps
            current_time += timedelta(hours=segment_time_hours)
            cumulative_distance += segment['distance']
        
        return analyzed_segments
    
    def get_closest_weather_data(self, df, target_time):
        """Trouve les données météo les plus proches du temps cible"""
        try:
            # Vérification que le DataFrame n'est pas vide
            if df.empty:
                return None
                
            # S'assurer que target_time est timezone-aware
            if target_time.tzinfo is None:
                target_time = self.timezone.localize(target_time)
                
            # Trouve l'index le plus proche
            time_diff = abs(df['date'] - target_time)
            closest_idx = time_diff.idxmin()
            
            weather_data = df.iloc[closest_idx].to_dict()
            
            # Vérification des valeurs manquantes et remplacement par des défauts
            defaults = {
                'wind_speed_10m': 10.0,  # Vent par défaut de 10 km/h
                'wind_direction_10m': 0.0,
                'temperature_2m': 15.0,
                'precipitation': 0.0,
                'precipitation_probability': 0.0
            }
            
            for key, default_value in defaults.items():
                if key not in weather_data or pd.isna(weather_data[key]):
                    weather_data[key] = default_value
            
            return weather_data
            
        except Exception as e:
            # En cas d'erreur, retourne des valeurs par défaut
            st.warning(f"Erreur lors de la recherche des données météo: {e}")
            return {
                'wind_speed_10m': 10.0,
                'wind_direction_10m': 0.0,
                'temperature_2m': 15.0,
                'precipitation': 0.0,
                'precipitation_probability': 0.0
            }
    
    def reverse_segments(self, segments):
        """Inverse l'ordre des segments pour simuler le parcours inverse"""
        reversed_segments = []
        
        for segment in reversed(segments):
            # Inverse les coordonnées et la direction
            reversed_bearing = (segment['bearing'] + 180) % 360
            
            reversed_segments.append({
                'start_lat': segment['end_lat'],
                'start_lon': segment['end_lon'],
                'end_lat': segment['start_lat'],
                'end_lon': segment['start_lon'],
                'distance': segment['distance'],
                'bearing': reversed_bearing,
                'cumulative_distance': segment['cumulative_distance']
            })
        
        return reversed_segments
    
    def analyze_route_geometry(self, points):
        """Analyse la géométrie du parcours pour proposer une nomenclature claire"""
        if len(points) < 3:
            return {"type": "insufficient_data"}
        
        start_point = points[0]
        end_point = points[-1]
        
        # Calculer la distance entre début et fin
        start_coords = (start_point['lat'], start_point['lon'])
        end_coords = (end_point['lat'], end_point['lon'])
        loop_closure_distance = geodesic(start_coords, end_coords).meters
        total_distance = sum(geodesic((points[i]['lat'], points[i]['lon']), 
                                    (points[i+1]['lat'], points[i+1]['lon'])).meters 
                            for i in range(len(points)-1))
        
        analysis = {
            'start_coords': start_coords,
            'end_coords': end_coords,
            'loop_closure_distance': loop_closure_distance,
            'total_distance': total_distance,
            'closure_ratio': loop_closure_distance / total_distance if total_distance > 0 else 1
        }
        
        # Classification du type de parcours
        if loop_closure_distance < 500:  # Boucle fermée (< 500m entre début et fin)
            analysis['type'] = 'loop'
            analysis['loop_direction'] = self.detect_loop_direction(points)
            # Ajout des points cardinaux pour clarification
            analysis['start_cardinal'] = self.get_cardinal_direction_from_coords(start_coords)
            analysis['main_bearing'] = self.calculate_main_bearing(points)
        elif analysis['closure_ratio'] < 0.1:  # Quasi-boucle
            analysis['type'] = 'quasi_loop'
            analysis['loop_direction'] = self.detect_loop_direction(points)
            analysis['start_cardinal'] = self.get_cardinal_direction_from_coords(start_coords)
            analysis['main_bearing'] = self.calculate_main_bearing(points)
        else:  # Trajet linéaire
            analysis['type'] = 'linear'
            analysis['main_direction'] = self.detect_main_direction(points)
            analysis['start_cardinal'] = self.get_cardinal_direction_from_coords(start_coords)
            analysis['end_cardinal'] = self.get_cardinal_direction_from_coords(end_coords)
        
        return analysis
    
    def get_cardinal_direction_from_coords(self, coords):
        """Détermine la direction cardinale approximative à partir des coordonnées"""
        lat, lon = coords
        
        # Classification simplifiée basée sur les coordonnées françaises
        if lat > 47:  # Nord de la France
            lat_desc = "Nord"
        elif lat > 45:  # Centre de la France
            lat_desc = "Centre"
        else:  # Sud de la France
            lat_desc = "Sud"
        
        if lon < 0:  # Ouest (rare en France)
            lon_desc = "Ouest"
        elif lon < 3:  # Ouest-Centre
            lon_desc = "Ouest"
        elif lon < 6:  # Centre-Est
            lon_desc = "Centre"
        else:  # Est
            lon_desc = "Est"
        
        return f"{lat_desc}-{lon_desc}"
    
    def calculate_main_bearing(self, points):
        """Calcule l'orientation principale du parcours"""
        if len(points) < 2:
            return 0
        
        # Utilise 10% des points pour éviter les micro-variations
        sample_size = max(2, len(points) // 10)
        bearings = []
        
        for i in range(0, len(points) - sample_size, sample_size):
            start_point = (points[i]['lat'], points[i]['lon'])
            end_point = (points[i + sample_size]['lat'], points[i + sample_size]['lon'])
            bearing = self.calculate_bearing(start_point, end_point)
            bearings.append(bearing)
        
        # Moyenne circulaire des directions
        if bearings:
            x_sum = sum(math.cos(math.radians(b)) for b in bearings)
            y_sum = sum(math.sin(math.radians(b)) for b in bearings)
            mean_bearing = math.degrees(math.atan2(y_sum, x_sum))
            return (mean_bearing + 360) % 360
        
        return 0

    def generate_route_nomenclature(self, geometry_analysis):
        """Génère une nomenclature claire et intuitive pour les deux sens possibles"""
        
        if geometry_analysis['type'] == 'loop':
            direction = geometry_analysis['loop_direction']
            start_area = geometry_analysis.get('start_cardinal', 'Départ')
            main_bearing = geometry_analysis.get('main_bearing', 0)
            bearing_cardinal = self.bearing_to_cardinal(main_bearing)
            
            return {
                'sense_a': {
                    'name': f"Sens {direction}",
                    'description': f"Boucle {direction} depuis {start_area} vers {bearing_cardinal}",
                    'emoji': "🔄" if direction == "horaire" else "🔃",
                    'detail': f"Direction principale: {bearing_cardinal} ({main_bearing:.0f}°)"
                },
                'sense_b': {
                    'name': f"Sens {'anti-horaire' if direction == 'horaire' else 'horaire'}",
                    'description': f"Boucle {'anti-horaire' if direction == 'horaire' else 'horaire'} depuis {start_area}",
                    'emoji': "🔃" if direction == "horaire" else "🔄",
                    'detail': f"Direction opposée: {self.get_opposite_cardinal(bearing_cardinal)}"
                }
            }
        
        elif geometry_analysis['type'] in ['quasi_loop', 'linear']:
            if 'main_direction' in geometry_analysis:
                direction = geometry_analysis['main_direction']
                cardinal = direction['cardinal']
                start_area = geometry_analysis.get('start_cardinal', '')
                end_area = geometry_analysis.get('end_cardinal', '')
                
                # Descriptions plus précises pour les trajets linéaires
                if geometry_analysis['type'] == 'linear' and start_area and end_area:
                    sense_a_desc = f"De {start_area} vers {end_area}"
                    sense_b_desc = f"De {end_area} vers {start_area}"
                else:
                    sense_a_desc = f"Direction {cardinal}"
                    sense_b_desc = f"Direction opposée"
                
                opposites = {
                    'Nord': 'Sud', 'Sud': 'Nord', 'Est': 'Ouest', 'Ouest': 'Est',
                    'Nord-Est': 'Sud-Ouest', 'Sud-Ouest': 'Nord-Est',
                    'Sud-Est': 'Nord-Ouest', 'Nord-Ouest': 'Sud-Est'
                }
                
                return {
                    'sense_a': {
                        'name': f"Vers {cardinal}",
                        'description': sense_a_desc,
                        'emoji': self.get_direction_emoji(cardinal),
                        'detail': f"Parcours principal ({direction['distance_km']:.1f}km à vol d'oiseau)"
                    },
                    'sense_b': {
                        'name': f"Vers {opposites.get(cardinal, 'retour')}",
                        'description': sense_b_desc,
                        'emoji': self.get_direction_emoji(opposites.get(cardinal, cardinal)),
                        'detail': f"Parcours de retour (même distance)"
                    }
                }
        
        # Fallback générique amélioré
        return {
            'sense_a': {
                'name': "Parcours A",
                'description': "Premier sens de parcours (tel que tracé)",
                'emoji': "➡️",
                'detail': "Sens d'origine du fichier GPX"
            },
            'sense_b': {
                'name': "Parcours B", 
                'description': "Sens inverse du parcours",
                'emoji': "⬅️",
                'detail': "Sens opposé au fichier GPX"
            }
        }

    def bearing_to_cardinal(self, bearing):
        """Convertit un angle en direction cardinale"""
        directions = [
            (0, "Nord"), (22.5, "Nord-Nord-Est"), (45, "Nord-Est"), (67.5, "Est-Nord-Est"),
            (90, "Est"), (112.5, "Est-Sud-Est"), (135, "Sud-Est"), (157.5, "Sud-Sud-Est"),
            (180, "Sud"), (202.5, "Sud-Sud-Ouest"), (225, "Sud-Ouest"), (247.5, "Ouest-Sud-Ouest"),
            (270, "Ouest"), (292.5, "Ouest-Nord-Ouest"), (315, "Nord-Ouest"), (337.5, "Nord-Nord-Ouest")
        ]
        
        # Normaliser l'angle
        bearing = bearing % 360
        
        # Trouver la direction la plus proche
        min_diff = 360
        best_direction = "Nord"
        
        for angle, direction in directions:
            diff = min(abs(bearing - angle), abs(bearing - angle - 360), abs(bearing - angle + 360))
            if diff < min_diff:
                min_diff = diff
                best_direction = direction
        
        # Simplifier les directions composées pour plus de lisibilité
        simplifications = {
            "Nord-Nord-Est": "Nord-Est", "Est-Nord-Est": "Nord-Est",
            "Est-Sud-Est": "Sud-Est", "Sud-Sud-Est": "Sud-Est",
            "Sud-Sud-Ouest": "Sud-Ouest", "Ouest-Sud-Ouest": "Sud-Ouest",
            "Ouest-Nord-Ouest": "Nord-Ouest", "Nord-Nord-Ouest": "Nord-Ouest"
        }
        
        return simplifications.get(best_direction, best_direction)

    def get_opposite_cardinal(self, cardinal):
        """Retourne la direction cardinale opposée"""
        opposites = {
            'Nord': 'Sud', 'Sud': 'Nord', 'Est': 'Ouest', 'Ouest': 'Est',
            'Nord-Est': 'Sud-Ouest', 'Sud-Ouest': 'Nord-Est',
            'Sud-Est': 'Nord-Ouest', 'Nord-Ouest': 'Sud-Est'
        }
        return opposites.get(cardinal, cardinal)

    # Modification de la fonction d'affichage pour utiliser les nouvelles informations
    def display_enhanced_analysis_results(optimizer, segments, weather, avg_speed, start_datetime, 
                                        geometry_analysis, nomenclature, total_distance):
        """Affiche les résultats d'analyse avec la nomenclature améliorée"""
        
        st.header("🔍 Analyse comparative intelligente")
        
        # Affichage du contexte géographique
        if geometry_analysis['type'] == 'loop':
            st.info(f"🔄 **Boucle détectée** - Départ: {geometry_analysis.get('start_cardinal', 'Position inconnue')}")
        elif geometry_analysis['type'] == 'linear':
            start_area = geometry_analysis.get('start_cardinal', '')
            end_area = geometry_analysis.get('end_cardinal', '')
            st.info(f"🗺️ **Trajet linéaire** - De {start_area} vers {end_area}")
        
        # Analyse dans les deux sens avec nouvelle nomenclature
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"{nomenclature['sense_a']['emoji']} {nomenclature['sense_a']['name']}")
            st.caption(nomenclature['sense_a']['description'])
            if 'detail' in nomenclature['sense_a']:
                st.caption(f"ℹ️ {nomenclature['sense_a']['detail']}")
            
            # Reste du code d'analyse...
            # (le reste du code reste identique)
        
        with col2:
            st.subheader(f"{nomenclature['sense_b']['emoji']} {nomenclature['sense_b']['name']}")
            st.caption(nomenclature['sense_b']['description'])
            if 'detail' in nomenclature['sense_b']:
                st.caption(f"ℹ️ {nomenclature['sense_b']['detail']}")

    def detect_loop_direction(self, points):
        """Détecte si une boucle est parcourue dans le sens horaire ou anti-horaire"""
        if len(points) < 4:
            return "indetermine"
        
        # Calcul de l'aire signée du polygone (formule du lacet)
        signed_area = 0
        n = len(points)
        
        for i in range(n-1):
            x1, y1 = points[i]['lon'], points[i]['lat']
            x2, y2 = points[i+1]['lon'], points[i+1]['lat']
            signed_area += (x2 - x1) * (y2 + y1)
        
        # Fermer le polygone si nécessaire
        if geodesic((points[0]['lat'], points[0]['lon']), 
                    (points[-1]['lat'], points[-1]['lon'])).meters > 500:
            x1, y1 = points[-1]['lon'], points[-1]['lat']
            x2, y2 = points[0]['lon'], points[0]['lat']
            signed_area += (x2 - x1) * (y2 + y1)
        
        # Aire positive = sens anti-horaire, négative = sens horaire
        return "anti-horaire" if signed_area > 0 else "horaire"

    def detect_main_direction(self, points):
        """Détecte la direction géographique principale d'un trajet linéaire"""
        start = points[0]
        end = points[-1]
        
        lat_diff = end['lat'] - start['lat']
        lon_diff = end['lon'] - start['lon']
        
        # Calculer l'azimut principal
        bearing = self.calculate_bearing((start['lat'], start['lon']), 
                                       (end['lat'], end['lon']))
        
        # Convertir en directions cardinales
        directions = [
            (0, "Nord"), (45, "Nord-Est"), (90, "Est"), (135, "Sud-Est"),
            (180, "Sud"), (225, "Sud-Ouest"), (270, "Ouest"), (315, "Nord-Ouest")
        ]
        
        # Trouver la direction la plus proche
        min_diff = 360
        main_direction = "Nord"
        
        for angle, direction in directions:
            diff = min(abs(bearing - angle), abs(bearing - angle - 360), abs(bearing - angle + 360))
            if diff < min_diff:
                min_diff = diff
                main_direction = direction
        
        return {
            'cardinal': main_direction,
            'bearing': bearing,
            'distance_km': geodesic((start['lat'], start['lon']), 
                                   (end['lat'], end['lon'])).kilometers,
            'emoji': self.get_direction_emoji(main_direction)
        }

    def get_direction_emoji(self, cardinal):
        """Retourne l'emoji approprié pour chaque direction"""
        emojis = {
            'Nord': '⬆️', 'Sud': '⬇️', 'Est': '➡️', 'Ouest': '⬅️',
            'Nord-Est': '↗️', 'Sud-Est': '↘️', 'Sud-Ouest': '↙️', 'Nord-Ouest': '↖️'
        }
        return emojis.get(cardinal, '🔄')

    def create_enhanced_map(self, analyzed_segments, title="Parcours", geometry_analysis=None):
        """Carte améliorée avec indications de direction et légende complète"""
        if not analyzed_segments:
            return None
        
        # Centre de la carte
        center_lat = np.mean([s['start_lat'] for s in analyzed_segments])
        center_lon = np.mean([s['start_lon'] for s in analyzed_segments])
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
        
        # Couleurs selon le type de vent
        color_map = {'face': '#ff4444', 'dos': '#44ff44', 'lateral': '#ff8844'}
        
        for i, segment in enumerate(analyzed_segments):
            color = color_map.get(segment['wind_type'], '#4444ff')
            
            # Popup avec plus d'infos
            popup_text = f"""
            <div style="font-family: Arial; font-size: 12px;">
            <b>Segment {i+1}/{len(analyzed_segments)}</b><br>
            <b>Vent:</b> {segment['wind_type']} ({segment['wind_impact']:.1f} km/h)<br>
            <b>Vitesse vent:</b> {segment['wind_speed']:.1f} km/h<br>
            <b>Direction vent:</b> {segment['wind_direction']:.0f}°<br>
            <b>Heure:</b> {segment['time']}<br>
            <b>Température:</b> {segment['temperature']:.1f}°C<br>
            <b>Distance:</b> {segment['distance']:.0f}m<br>
            <b>Cap:</b> {segment['bearing']:.0f}°
            </div>
            """
            
            folium.PolyLine(
                locations=[
                    [segment['start_lat'], segment['start_lon']],
                    [segment['end_lat'], segment['end_lon']]
                ],
                color=color,
                weight=4,
                opacity=0.8,
                popup=folium.Popup(popup_text, max_width=300)
            ).add_to(m)
        
        # Marqueurs de départ et arrivée avec plus d'infos
        start_seg = analyzed_segments[0]
        end_seg = analyzed_segments[-1]
        
        # Marqueur de départ
        folium.Marker(
            [start_seg['start_lat'], start_seg['start_lon']],
            popup=folium.Popup(
                f"""<b>DÉPART</b><br>
                Heure: {start_seg['time']}<br>
                Température: {start_seg['temperature']:.1f}°C<br>
                Vent: {start_seg['wind_speed']:.1f} km/h<br>
                Précipitations: {start_seg['precipitation_probability']:.0f}%""",
                max_width=200
            ),
            tooltip="Point de départ",
            icon=folium.Icon(color='green', icon='play', prefix='fa')
        ).add_to(m)
        
        # Marqueur d'arrivée
        folium.Marker(
            [end_seg['end_lat'], end_seg['end_lon']],
            popup=folium.Popup(
                f"""<b>ARRIVÉE</b><br>
                Heure: {end_seg['time']}<br>
                Température: {end_seg['temperature']:.1f}°C<br>
                Vent: {end_seg['wind_speed']:.1f} km/h<br>
                Précipitations: {end_seg['precipitation_probability']:.0f}%""",
                max_width=200
            ),
            tooltip="Point d'arrivée",
            icon=folium.Icon(color='red', icon='stop', prefix='fa')
        ).add_to(m)
        
        # Flèches de direction tous les 10 segments ou minimum 5
        step = max(1, len(analyzed_segments) // 10)
        for i in range(0, len(analyzed_segments), step):
            segment = analyzed_segments[i]
            mid_lat = (segment['start_lat'] + segment['end_lat']) / 2
            mid_lon = (segment['start_lon'] + segment['end_lon']) / 2
            
            # Emoji de flèche selon la direction
            arrow_rotation = segment['bearing']
            if 0 <= arrow_rotation < 45 or 315 <= arrow_rotation < 360:
                arrow = "⬆️"
            elif 45 <= arrow_rotation < 135:
                arrow = "➡️"
            elif 135 <= arrow_rotation < 225:
                arrow = "⬇️"
            else:
                arrow = "⬅️"
            
            folium.Marker(
                [mid_lat, mid_lon],
                icon=folium.DivIcon(
                    html=f'<div style="color: #333; font-size: 16px; text-align: center;">{arrow}</div>',
                    icon_size=(20, 20),
                    icon_anchor=(10, 10)
                )
            ).add_to(m)
        
        # Marqueur du centre GPS
        folium.Marker(
            [center_lat, center_lon],
            popup=folium.Popup(
                f"""<b>Centre GPS de la trace</b><br>
                Coordonnées envoyées à Open-Meteo<br>
                Lat: {center_lat:.6f}°<br>
                Lon: {center_lon:.6f}°""",
                max_width=200
            ),
            tooltip="Coordonnées météo",
            icon=folium.Icon(color='blue', icon='crosshairs', prefix='fa')
        ).add_to(m)
        
        # Légende améliorée avec statistiques
        total_distance = sum(s['distance'] for s in analyzed_segments) / 1000
        face_distance = sum(s['distance'] for s in analyzed_segments if s['wind_type'] == 'face') / 1000
        dos_distance = sum(s['distance'] for s in analyzed_segments if s['wind_type'] == 'dos') / 1000
        lateral_distance = sum(s['distance'] for s in analyzed_segments if s['wind_type'] == 'lateral') / 1000
        
        legend_html = f"""
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 220px; height: 280px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:11px; padding: 10px; border-radius: 5px;
                    box-shadow: 0 0 15px rgba(0,0,0,0.2);">
        <p><b>📊 {title}</b></p>
        <p><b>Légende des couleurs:</b></p>
        <p><i class="fa fa-minus" style="color:#ff4444"></i> Vent de face ({face_distance:.1f}km)</p>
        <p><i class="fa fa-minus" style="color:#44ff44"></i> Vent de dos ({dos_distance:.1f}km)</p>
        <p><i class="fa fa-minus" style="color:#ff8844"></i> Vent latéral ({lateral_distance:.1f}km)</p>
        <hr>
        <p><b>Marqueurs:</b></p>
        <p><i class="fa fa-play" style="color:green"></i> Départ</p>
        <p><i class="fa fa-stop" style="color:red"></i> Arrivée</p>
        <p><i class="fa fa-crosshairs" style="color:blue"></i> Centre GPS</p>
        <p>⬆️➡️⬇️⬅️ Direction du parcours</p>
        <hr>
        <p><b>Total:</b> {total_distance:.1f} km</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m

def display_enhanced_analysis_results(optimizer, segments, weather, avg_speed, start_datetime, 
                                    geometry_analysis, nomenclature, total_distance):
    """Affiche les résultats d'analyse avec la nomenclature améliorée"""
    
    st.header("🔍 Analyse comparative intelligente")
    
    # Affichage du contexte géographique
    if geometry_analysis['type'] == 'loop':
        st.info(f"🔄 **Boucle détectée** - Départ: {geometry_analysis.get('start_cardinal', 'Position inconnue')}")
    elif geometry_analysis['type'] == 'linear':
        start_area = geometry_analysis.get('start_cardinal', '')
        end_area = geometry_analysis.get('end_cardinal', '')
        st.info(f"🗺️ **Trajet linéaire** - De {start_area} vers {end_area}")
    
    # Analyse dans les deux sens avec nouvelle nomenclature
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"{nomenclature['sense_a']['emoji']} {nomenclature['sense_a']['name']}")
        st.caption(nomenclature['sense_a']['description'])
        if 'detail' in nomenclature['sense_a']:
            st.caption(f"ℹ️ {nomenclature['sense_a']['detail']}")
        
        sense_a_analysis = optimizer.analyze_wind_impact_temporal(
            segments, weather, avg_speed, start_datetime
        )
        
        # Statistiques
        face_distance = sum(s['distance'] for s in sense_a_analysis if s['wind_type'] == 'face')
        dos_distance = sum(s['distance'] for s in sense_a_analysis if s['wind_type'] == 'dos')
        lateral_distance = sum(s['distance'] for s in sense_a_analysis if s['wind_type'] == 'lateral')
        avg_wind_speed = np.mean([s['wind_speed'] for s in sense_a_analysis])
        
        # Métriques avec pourcentages
        col1_1, col1_2 = st.columns(2)
        with col1_1:
            st.metric("🔴 Vent de face", f"{face_distance/1000:.1f} km")
            st.metric("🟢 Vent de dos", f"{dos_distance/1000:.1f} km")
        with col1_2:
            st.metric("Pourcentage défavorable", f"{face_distance/total_distance*100:.0f}%")
            st.metric("Pourcentage favorable", f"{dos_distance/total_distance*100:.0f}%")
        
        st.metric("🟠 Vent latéral", f"{lateral_distance/1000:.1f} km ({lateral_distance/total_distance*100:.0f}%)")
        st.metric("💨 Vent moyen", f"{avg_wind_speed:.1f} km/h")
        
        # Score de favorabilité
        favorability_score = (dos_distance - face_distance) / total_distance * 100
        score_color = "normal" if -5 <= favorability_score <= 5 else ("normal" if favorability_score > 0 else "normal")
        st.metric("⭐ Score de favorabilité", f"{favorability_score:+.1f}%", help="Score positif = plus favorable")
        
        # Informations supplémentaires
        temps_estime = total_distance / 1000 / avg_speed * 60
        temp_debut = sense_a_analysis[0]['temperature']
        temp_fin = sense_a_analysis[-1]['temperature']
        pluie_moyenne = np.mean([s['precipitation_probability'] for s in sense_a_analysis])
        
        with st.expander("📋 Détails du parcours"):
            st.write(f"**Durée estimée:** {temps_estime:.0f} minutes")
            st.write(f"**Température de départ:** {temp_debut:.1f}°C")
            st.write(f"**Température d'arrivée:** {temp_fin:.1f}°C")
            st.write(f"**Évolution température:** {temp_fin-temp_debut:+.1f}°C")
            st.write(f"**Risque de pluie moyen:** {pluie_moyenne:.0f}%")
        
        # Carte améliorée
        map_sense_a = optimizer.create_enhanced_map(
            sense_a_analysis, 
            nomenclature['sense_a']['name'], 
            geometry_analysis
        )
        if map_sense_a:
            folium_static(map_sense_a)
    
    with col2:
        st.subheader(f"{nomenclature['sense_b']['emoji']} {nomenclature['sense_b']['name']}")
        st.caption(nomenclature['sense_b']['description'])
        if 'detail' in nomenclature['sense_b']:
            st.caption(f"ℹ️ {nomenclature['sense_b']['detail']}")

        reversed_segments = optimizer.reverse_segments(segments)
        sense_b_analysis = optimizer.analyze_wind_impact_temporal(
            reversed_segments, weather, avg_speed, start_datetime
        )
        
        # Statistiques
        face_distance_b = sum(s['distance'] for s in sense_b_analysis if s['wind_type'] == 'face')
        dos_distance_b = sum(s['distance'] for s in sense_b_analysis if s['wind_type'] == 'dos')
        lateral_distance_b = sum(s['distance'] for s in sense_b_analysis if s['wind_type'] == 'lateral')
        avg_wind_speed_b = np.mean([s['wind_speed'] for s in sense_b_analysis])
        
        # Métriques avec pourcentages
        col2_1, col2_2 = st.columns(2)
        with col2_1:
            st.metric("🔴 Vent de face", f"{face_distance_b/1000:.1f} km")
            st.metric("🟢 Vent de dos", f"{dos_distance_b/1000:.1f} km")
        with col2_2:
            st.metric("Pourcentage défavorable", f"{face_distance_b/total_distance*100:.0f}%")
            st.metric("Pourcentage favorable", f"{dos_distance_b/total_distance*100:.0f}%")
        
        st.metric("🟠 Vent latéral", f"{lateral_distance_b/1000:.1f} km ({lateral_distance_b/total_distance*100:.0f}%)")
        st.metric("💨 Vent moyen", f"{avg_wind_speed_b:.1f} km/h")
        
        # Score de favorabilité
        favorability_score_b = (dos_distance_b - face_distance_b) / total_distance * 100
        st.metric("⭐ Score de favorabilité", f"{favorability_score_b:+.1f}%", help="Score positif = plus favorable")
        
        # Informations supplémentaires
        temp_debut_b = sense_b_analysis[0]['temperature']
        temp_fin_b = sense_b_analysis[-1]['temperature']
        pluie_moyenne_b = np.mean([s['precipitation_probability'] for s in sense_b_analysis])
        
        with st.expander("📋 Détails du parcours"):
            st.write(f"**Durée estimée:** {temps_estime:.0f} minutes")
            st.write(f"**Température de départ:** {temp_debut_b:.1f}°C")
            st.write(f"**Température d'arrivée:** {temp_fin_b:.1f}°C")
            st.write(f"**Évolution température:** {temp_fin_b-temp_debut_b:+.1f}°C")
            st.write(f"**Risque de pluie moyen:** {pluie_moyenne_b:.0f}%")
        
        # Carte améliorée
        map_sense_b = optimizer.create_enhanced_map(
            sense_b_analysis, 
            nomenclature['sense_b']['name'], 
            geometry_analysis
        )
        if map_sense_b:
            folium_static(map_sense_b)
    
    # Calcul des conforts thermiques (moved here to always define them)
    temp_comfort_a = 25 - abs(np.mean([temp_debut, temp_fin]) - 20)  # Optimal autour de 20°C
    temp_comfort_b = 25 - abs(np.mean([temp_debut_b, temp_fin_b]) - 20)
    
    # Recommandation intelligente avec contexte géométrique
    st.header("🎯 Recommandation intelligente")
    
    score_difference = favorability_score - favorability_score_b
    abs_difference = abs(score_difference)
    
    # Contexte géométrique pour la recommandation
    geometric_context = ""
    if geometry_analysis['type'] == 'loop':
        geometric_context = f"sur cette boucle {geometry_analysis['loop_direction']}"
    elif geometry_analysis['type'] == 'linear':
        direction = geometry_analysis['main_direction']['cardinal']
        geometric_context = f"sur ce trajet orienté {direction}"
    else:
        geometric_context = "sur ce parcours"
    
    # Interface de recommandation améliorée
    if abs_difference < 2:  # Différence négligeable
        st.info(f"🤝 **Les deux sens sont quasi équivalents** {geometric_context}")
        st.write(f"Différence négligeable de {abs_difference:.1f}% entre les deux options")
        
        # Critères secondaires avec scoring
        st.subheader("⚖️ Critères de départage")
        
        # Comparaison des critères secondaires
        criteria_scores = []
        
        # Critère température
        temp_winner = "A" if temp_comfort_a > temp_comfort_b else "B" if temp_comfort_b > temp_comfort_a else "Égalité"
        
        # Critère pluie
        rain_winner = "A" if pluie_moyenne < pluie_moyenne_b else "B" if pluie_moyenne_b < pluie_moyenne else "Égalité"
        
        # Critère évolution température
        temp_evolution_a = abs(temp_fin - temp_debut)
        temp_evolution_b = abs(temp_fin_b - temp_debut_b)
        temp_stability_winner = "A" if temp_evolution_a < temp_evolution_b else "B" if temp_evolution_b < temp_evolution_a else "Égalité"
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🌡️ Confort thermique", temp_winner, 
                     f"A: {np.mean([temp_debut, temp_fin]):.1f}°C vs B: {np.mean([temp_debut_b, temp_fin_b]):.1f}°C")
        with col2:
            st.metric("🌧️ Risque de pluie", rain_winner,
                     f"A: {pluie_moyenne:.0f}% vs B: {pluie_moyenne_b:.0f}%")
        with col3:
            st.metric("🔄 Stabilité thermique", temp_stability_winner,
                     f"A: ±{temp_evolution_a:.1f}°C vs B: ±{temp_evolution_b:.1f}°C")
        
        # Conseil personnalisé
        if temp_winner != "Égalité" or rain_winner != "Égalité":
            if temp_winner == "A" and rain_winner == "A":
                st.success(f"💡 **Léger avantage pour {nomenclature['sense_a']['name']}** sur les critères météo")
            elif temp_winner == "B" and rain_winner == "B":
                st.success(f"💡 **Léger avantage pour {nomenclature['sense_b']['name']}** sur les critères météo")
            else:
                st.info("🎲 **Choix libre** - Les deux options sont vraiment équivalentes. Suivez votre préférence !")
        else:
            st.info("🎯 **Parfaitement équivalent** - Choisissez selon vos préférences personnelles")
    
    elif score_difference > 2:  # Sens A meilleur
        advantage_level = "forte" if abs_difference < 10 else "très forte" if abs_difference < 20 else "majeure"
        st.success(f"🏆 **Recommandation {advantage_level}: {nomenclature['sense_a']['name']}** {geometric_context}")
        st.write(f"**Avantage significatif:** {score_difference:.1f}% de conditions plus favorables")
        
        # Impact concret
        advantage_km = (score_difference / 100) * total_distance / 1000
        advantage_time = advantage_km / avg_speed * 60  # minutes économisées
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📏 Avantage distance", f"{advantage_km:.1f} km", "de vent plus favorable")
        with col2:
            st.metric("⏱️ Gain de temps estimé", f"{advantage_time:.0f} min", "d'effort économisé")
        with col3:
            st.metric("💪 Niveau d'impact", advantage_level, f"{abs_difference:.1f}% d'écart")
        
        if abs_difference > 15:
            st.warning("⚠️ **Impact majeur** - Cette différence sera très perceptible durant votre sortie !")
    
    else:  # Sens B meilleur
        advantage_level = "forte" if abs_difference < 10 else "très forte" if abs_difference < 20 else "majeure"
        st.success(f"🏆 **Recommandation {advantage_level}: {nomenclature['sense_b']['name']}** {geometric_context}")
        st.write(f"**Avantage significatif:** {abs_difference:.1f}% de conditions plus favorables")
        
        # Impact concret
        advantage_km = (abs_difference / 100) * total_distance / 1000
        advantage_time = advantage_km / avg_speed * 60  # minutes économisées
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📏 Avantage distance", f"{advantage_km:.1f} km", "de vent plus favorable")
        with col2:
            st.metric("⏱️ Gain de temps estimé", f"{advantage_time:.0f} min", "d'effort économisé")
        with col3:
            st.metric("💪 Niveau d'impact", advantage_level, f"{abs_difference:.1f}% d'écart")
        
        if abs_difference > 15:
            st.warning("⚠️ **Impact majeur** - Cette différence sera très perceptible durant votre sortie !")
    
    # Analyse des vents dominants
    st.subheader("🌪️ Analyse des vents dominants")
    
    # Calcul des directions de vent les plus fréquentes
    wind_directions_a = [s['wind_direction'] for s in sense_a_analysis]
    wind_speeds_a = [s['wind_speed'] for s in sense_a_analysis]
    
    # Regroupement par secteurs de 45°
    wind_sectors = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    sector_data = {sector: {'count': 0, 'avg_speed': 0, 'total_speed': 0} for sector in wind_sectors}
    
    for direction, speed in zip(wind_directions_a, wind_speeds_a):
        sector_index = int((direction + 22.5) // 45) % 8
        sector = wind_sectors[sector_index]
        sector_data[sector]['count'] += 1
        sector_data[sector]['total_speed'] += speed
    
    for sector in sector_data:
        if sector_data[sector]['count'] > 0:
            sector_data[sector]['avg_speed'] = sector_data[sector]['total_speed'] / sector_data[sector]['count']
    
    # Secteur dominant
    dominant_sector = max(sector_data.keys(), key=lambda x: sector_data[x]['count'])
    dominant_speed = sector_data[dominant_sector]['avg_speed']
    dominant_percentage = (sector_data[dominant_sector]['count'] / len(wind_directions_a)) * 100
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🧭 Vent dominant", dominant_sector, f"{dominant_percentage:.0f}% du temps")
    with col2:
        st.metric("💨 Vitesse moyenne", f"{np.mean(wind_speeds_a):.1f} km/h", "sur tout le parcours")
    with col3:
        st.metric("🎯 Vitesse dominante", f"{dominant_speed:.1f} km/h", f"secteur {dominant_sector}")
    
    # Graphique en rose des vents simplifié
    sectors = list(sector_data.keys())
    counts = [sector_data[s]['count'] for s in sectors]
    speeds = [sector_data[s]['avg_speed'] for s in sectors]
    
    fig_wind_rose = go.Figure()
    
    fig_wind_rose.add_trace(go.Scatterpolar(
        r=counts,
        theta=sectors,
        fill='toself',
        name='Fréquence des vents',
        line_color='blue'
    ))
    
    fig_wind_rose.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, max(counts)]),
            angularaxis=dict(rotation=90, direction='clockwise')
        ),
        title="Rose des vents - Fréquence par secteur",
        height=400
    )
    
    st.plotly_chart(fig_wind_rose, use_container_width=True)
    
    # Graphique comparatif final avec nouvelle nomenclature
    st.header("📊 Comparaison visuelle détaillée")
    
    comparison_data = {
        'Sens de parcours': [nomenclature['sense_a']['name'], nomenclature['sense_b']['name']],
        'Vent de face (km)': [face_distance/1000, face_distance_b/1000],
        'Vent de dos (km)': [dos_distance/1000, dos_distance_b/1000], 
        'Vent latéral (km)': [lateral_distance/1000, lateral_distance_b/1000],
        'Score favorabilité (%)': [favorability_score, favorability_score_b],
        'Vitesse vent moyenne (km/h)': [avg_wind_speed, avg_wind_speed_b],
        'Risque pluie (%)': [pluie_moyenne, pluie_moyenne_b]
    }
    
    df_comparison = pd.DataFrame(comparison_data)
    
    # Graphique en barres empilées
    fig_stacked = px.bar(
        df_comparison, 
        x='Sens de parcours',
        y=['Vent de face (km)', 'Vent de dos (km)', 'Vent latéral (km)'],
        title="Répartition des conditions de vent par sens de parcours",
        color_discrete_map={
            'Vent de face (km)': '#ff4444',
            'Vent de dos (km)': '#44ff44', 
            'Vent latéral (km)': '#ff8844'
        },
        text_auto='.1f'
    )
    fig_stacked.update_layout(height=400, xaxis_title="", yaxis_title="Distance (km)")
    st.plotly_chart(fig_stacked, use_container_width=True)
    
    # Graphique des scores de favorabilité
    colors = ['#44ff44' if score > 0 else '#ff4444' if score < -5 else '#ff8844' 
              for score in df_comparison['Score favorabilité (%)']]
    
    fig_scores = px.bar(
        df_comparison,
        x='Sens de parcours', 
        y='Score favorabilité (%)',
        title="Score de favorabilité par sens (plus c'est haut, mieux c'est)",
        color='Score favorabilité (%)',
        color_continuous_scale=['red', 'orange', 'green'],
        text='Score favorabilité (%)'
    )
    fig_scores.update_layout(height=350, showlegend=False, xaxis_title="", yaxis_title="Score (%)")
    fig_scores.add_hline(y=0, line_dash="dash", line_color="gray", 
                        annotation_text="Neutralité", annotation_position="top right")
    fig_scores.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_scores, use_container_width=True)
    
    # Graphique radar comparatif
    categories = ['Vent favorable', 'Vitesse vent faible', 'Risque pluie faible', 'Confort thermique']
    
    # Normalisation des scores (0-100)
    def normalize_score(value, min_val, max_val, inverse=False):
        if max_val == min_val:
            return 50
        normalized = (value - min_val) / (max_val - min_val) * 100
        return 100 - normalized if inverse else normalized
    
    # Calcul des scores normalisés
    all_fav_scores = [favorability_score, favorability_score_b]
    all_wind_speeds = [avg_wind_speed, avg_wind_speed_b]
    all_rain_probs = [pluie_moyenne, pluie_moyenne_b]
    all_temp_comforts = [temp_comfort_a, temp_comfort_b]
    
    sense_a_radar = [
        normalize_score(favorability_score, min(all_fav_scores), max(all_fav_scores)),
        normalize_score(avg_wind_speed, min(all_wind_speeds), max(all_wind_speeds), inverse=True),
        normalize_score(pluie_moyenne, min(all_rain_probs), max(all_rain_probs), inverse=True),
        normalize_score(temp_comfort_a, min(all_temp_comforts), max(all_temp_comforts))
    ]
    
    sense_b_radar = [
        normalize_score(favorability_score_b, min(all_fav_scores), max(all_fav_scores)),
        normalize_score(avg_wind_speed_b, min(all_wind_speeds), max(all_wind_speeds), inverse=True),
        normalize_score(pluie_moyenne_b, min(all_rain_probs), max(all_rain_probs), inverse=True),
        normalize_score(temp_comfort_b, min(all_temp_comforts), max(all_temp_comforts))
    ]
    
    fig_radar = go.Figure()
    
    fig_radar.add_trace(go.Scatterpolar(
        r=sense_a_radar + [sense_a_radar[0]],  # Fermer le polygone
        theta=categories + [categories[0]],
        fill='toself',
        name=nomenclature['sense_a']['name'],
        line_color='blue'
    ))
    
    fig_radar.add_trace(go.Scatterpolar(
        r=sense_b_radar + [sense_b_radar[0]],  # Fermer le polygone
        theta=categories + [categories[0]],
        fill='toself',
        name=nomenclature['sense_b']['name'],
        line_color='red'
    ))
    
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        ),
        title="Comparaison radar des critères (100 = optimal)",
        height=500
    )
    
    st.plotly_chart(fig_radar, use_container_width=True)
    
    return {
        'sense_a': sense_a_analysis,
        'sense_b': sense_b_analysis,
        'scores': {
            'sense_a': favorability_score,
            'sense_b': favorability_score_b,
            'difference': score_difference
        },
        'recommendation': nomenclature['sense_a']['name'] if score_difference > 2 
                         else nomenclature['sense_b']['name'] if score_difference < -2 
                         else "Équivalent",
        'detailed_stats': {
            'sense_a': {
                'face_km': face_distance/1000,
                'dos_km': dos_distance/1000,
                'lateral_km': lateral_distance/1000,
                'avg_wind': avg_wind_speed,
                'rain_prob': pluie_moyenne,
                'temp_start': temp_debut,
                'temp_end': temp_fin
            },
            'sense_b': {
                'face_km': face_distance_b/1000,
                'dos_km': dos_distance_b/1000,
                'lateral_km': lateral_distance_b/1000,
                'avg_wind': avg_wind_speed_b,
                'rain_prob': pluie_moyenne_b,
                'temp_start': temp_debut_b,
                'temp_end': temp_fin_b
            }
        }
    }

def create_enhanced_summary_widget(geometry_analysis, nomenclature):
    """Widget résumé amélioré avec infos géométriques"""
    
    with st.container():
        st.markdown("""
        <div style="padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    border-radius: 15px; margin: 15px 0; color: white;">
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col1:
            if geometry_analysis['type'] == 'loop':
                st.markdown("### 🔄")
                st.write("**Boucle**")
            elif geometry_analysis['type'] == 'linear':
                direction_emoji = geometry_analysis['main_direction']['emoji']
                st.markdown(f"### {direction_emoji}")
                st.write("**Linéaire**")
            else:
                st.markdown("### 🗺️")
                st.write("**Parcours**")
        
        with col2:
            st.markdown("### 🎯 Analyse intelligente du parcours")
            
            if geometry_analysis['type'] == 'loop':
                direction = geometry_analysis['loop_direction']
                closure_dist = geometry_analysis['loop_closure_distance']
                st.write(f"**Boucle {direction}** détectée (fermeture {closure_dist:.0f}m)")
                st.write(f"**Comparaison:** {nomenclature['sense_a']['name']} vs {nomenclature['sense_b']['name']}")
            
            else:
                st.write(f"**Parcours analysé** - Optimisation météorologique")
                st.write(f"**Options:** {nomenclature['sense_a']['name']} vs {nomenclature['sense_b']['name']}")
        
        with col3:
            st.markdown("### 📊")
            st.write("**Prêt !**")
            st.write("Résultats ci-dessous")
        
        st.markdown("</div>", unsafe_allow_html=True)

def display_weather_forecast_summary(weather_data, start_datetime):
    """Affiche un résumé des prévisions météo avec graphiques avancés"""
    
    st.subheader("🌦️ Conditions météorologiques prévues")
    
    hourly_df = weather_data['hourly_data']
    start_date = start_datetime.date()
    
    # Filtrer les données pour la journée de départ
    weather_today = hourly_df[hourly_df['date'].dt.date == start_date].copy()
    
    if len(weather_today) > 0:
        # Statistiques du jour
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            min_temp = weather_today['temperature_2m'].min()
            max_temp = weather_today['temperature_2m'].max()
            st.metric("🌡️ Température", f"{min_temp:.0f}°C - {max_temp:.0f}°C")
        
        with col2:
            avg_wind = weather_today['wind_speed_10m'].mean()
            max_wind = weather_today['wind_speed_10m'].max()
            st.metric("💨 Vent", f"{avg_wind:.0f} km/h (max {max_wind:.0f})")
        
        with col3:
            max_rain_prob = weather_today['precipitation_probability'].max()
            total_precip = weather_today['precipitation'].sum()
            st.metric("🌧️ Pluie", f"{max_rain_prob:.0f}% ({total_precip:.1f}mm)")
        
        with col4:
            max_gust = weather_today['wind_gusts_10m'].max()
            st.metric("💨 Rafales max", f"{max_gust:.0f} km/h")
        
        # Graphiques détaillés
        weather_today['hour'] = weather_today['date'].dt.hour
        
        # Graphique combiné température et vent
        fig_combined = go.Figure()
        
        # Température
        fig_combined.add_trace(go.Scatter(
            x=weather_today['hour'],
            y=weather_today['temperature_2m'],
            mode='lines+markers',
            name='Température (°C)',
            line=dict(color='red', width=3),
            yaxis='y1'
        ))
        
        # Vitesse du vent
        fig_combined.add_trace(go.Scatter(
            x=weather_today['hour'],
            y=weather_today['wind_speed_10m'],
            mode='lines+markers',
            name='Vent (km/h)',
            line=dict(color='blue', width=2),
            yaxis='y2'
        ))
        
        # Probabilité de pluie (aire)
        fig_combined.add_trace(go.Scatter(
            x=weather_today['hour'],
            y=weather_today['precipitation_probability'],
            mode='lines',
            name='Risque pluie (%)',
            fill='tonexty',
            fillcolor='rgba(135,206,250,0.3)',
            line=dict(color='lightblue', width=1),
            yaxis='y3'
        ))
        
        fig_combined.update_layout(
            title=f"Conditions météo du {start_date.strftime('%d/%m/%Y')}",
            xaxis_title="Heure",
            yaxis=dict(title="Température (°C)", titlefont=dict(color="red"), tickfont=dict(color="red")),
            yaxis2=dict(title="Vent (km/h)", titlefont=dict(color="blue"), tickfont=dict(color="blue"), 
                       anchor="x", overlaying="y", side="right"),
            yaxis3=dict(title="Pluie (%)", titlefont=dict(color="lightblue"), tickfont=dict(color="lightblue"), 
                       anchor="free", overlaying="y", side="right", position=0.85),
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_combined, use_container_width=True)
        
        # Direction du vent (graphique polaire)
        fig_wind_dir = go.Figure()
        
        fig_wind_dir.add_trace(go.Scatterpolar(
            r=weather_today['wind_speed_10m'],
            theta=weather_today['wind_direction_10m'],
            mode='markers+lines',
            name='Direction et force du vent',
            marker=dict(size=8, color=weather_today['hour'], 
                       colorscale='Viridis', showscale=True, 
                       colorbar=dict(title="Heure")),
            line=dict(color='gray', width=1)
        ))
        
        fig_wind_dir.update_layout(
            title="Évolution de la direction du vent dans la journée",
            polar=dict(
                radialaxis=dict(title="Vitesse (km/h)", visible=True),
                angularaxis=dict(rotation=90, direction='clockwise')
            ),
            height=400
        )
        
        st.plotly_chart(fig_wind_dir, use_container_width=True)
    
    else:
        st.warning("Données météo non disponibles pour cette date")

def generate_comprehensive_report(geometry_analysis, nomenclature, analysis_results, 
                                weather_data, total_distance, avg_speed, start_datetime, uploaded_file):
    """Génère un rapport complet avec toutes les analyses"""
    
    st.header("📄 Rapport d'analyse complet")
    
    # Détermination de la recommandation finale
    score_diff = analysis_results['scores']['difference']
    if abs(score_diff) < 2:
        recommendation_level = "équivalent"
        recommendation_icon = "🤝"
    elif abs(score_diff) < 10:
        recommendation_level = "avantage modéré"
        recommendation_icon = "👍"
    else:
        recommendation_level = "avantage fort"
        recommendation_icon = "🏆"
    
    # Résumé exécutif
    with st.expander("📋 Résumé exécutif", expanded=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("### 🎯 Recommandation finale")
            if analysis_results['recommendation'] == "Équivalent":
                st.info(f"{recommendation_icon} **Les deux sens sont équivalents**\n\n"
                       f"Différence de score: {abs(score_diff):.1f}% - Choisissez selon vos préférences")
            else:
                st.success(f"{recommendation_icon} **{analysis_results['recommendation']} recommandé**\n\n"
                          f"Avantage: {abs(score_diff):.1f}% ({recommendation_level})")
            
            # Contexte géométrique
            if geometry_analysis['type'] == 'loop':
                st.write(f"**Parcours:** Boucle {geometry_analysis['loop_direction']} "
                        f"({geometry_analysis['loop_closure_distance']:.0f}m de fermeture)")
            elif geometry_analysis['type'] == 'linear':
                direction = geometry_analysis['main_direction']
                st.write(f"**Parcours:** Trajet {direction['cardinal']} "
                        f"({direction['distance_km']:.1f}km en ligne directe)")
        
        with col2:
            st.write("### 📊 Statistiques clés")
            st.metric("Distance totale", f"{total_distance/1000:.1f} km")
            st.metric("Durée estimée", f"{total_distance/1000/avg_speed*60:.0f} min")
            st.metric("Points GPS", len(weather_data.get('hourly_data', [])))
            st.metric("Vitesse moyenne", f"{avg_speed} km/h")
    
    # Détails des analyses
    with st.expander("🔍 Analyse détaillée par sens"):
        
        tab1, tab2 = st.tabs([f"{nomenclature['sense_a']['emoji']} {nomenclature['sense_a']['name']}", 
                             f"{nomenclature['sense_b']['emoji']} {nomenclature['sense_b']['name']}"])
        
        with tab1:
            stats_a = analysis_results['detailed_stats']['sense_a']
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**Conditions de vent:**")
                st.write(f"• Vent de face: {stats_a['face_km']:.1f} km")
                st.write(f"• Vent de dos: {stats_a['dos_km']:.1f} km")
                st.write(f"• Vent latéral: {stats_a['lateral_km']:.1f} km")
            
            with col2:
                st.write("**Météorologie:**")
                st.write(f"• Vent moyen: {stats_a['avg_wind']:.1f} km/h")
                st.write(f"• Risque pluie: {stats_a['rain_prob']:.0f}%")
                st.write(f"• Score: {analysis_results['scores']['sense_a']:+.1f}%")
            
            with col3:
                st.write("**Température:**")
                st.write(f"• Départ: {stats_a['temp_start']:.1f}°C")
                st.write(f"• Arrivée: {stats_a['temp_end']:.1f}°C")
                st.write(f"• Évolution: {stats_a['temp_end']-stats_a['temp_start']:+.1f}°C")
        
        with tab2:
            stats_b = analysis_results['detailed_stats']['sense_b']
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**Conditions de vent:**")
                st.write(f"• Vent de face: {stats_b['face_km']:.1f} km")
                st.write(f"• Vent de dos: {stats_b['dos_km']:.1f} km")
                st.write(f"• Vent latéral: {stats_b['lateral_km']:.1f} km")
            
            with col2:
                st.write("**Météorologie:**")
                st.write(f"• Vent moyen: {stats_b['avg_wind']:.1f} km/h")
                st.write(f"• Risque pluie: {stats_b['rain_prob']:.0f}%")
                st.write(f"• Score: {analysis_results['scores']['sense_b']:+.1f}%")
            
            with col3:
                st.write("**Température:**")
                st.write(f"• Départ: {stats_b['temp_start']:.1f}°C")
                st.write(f"• Arrivée: {stats_b['temp_end']:.1f}°C")
                st.write(f"• Évolution: {stats_b['temp_end']-stats_b['temp_start']:+.1f}°C")
    
    # Données techniques
    with st.expander("🔧 Informations techniques"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Coordonnées GPS:**")
            center_coords = weather_data['center_coordinates']
            actual_coords = weather_data['actual_coordinates']
            st.write(f"• Centre trace: {center_coords['lat']:.6f}°, {center_coords['lon']:.6f}°")
            st.write(f"• Open-Meteo: {actual_coords['lat']:.6f}°, {actual_coords['lon']:.6f}°")
            st.write(f"• Altitude: {weather_data['elevation']:.0f}m")
            st.write(f"• Fuseau horaire: {weather_data['timezone']}")
        
        with col2:
            st.write("**Paramètres d'analyse:**")
            st.write(f"• Fichier GPX: {uploaded_file.name}")
            st.write(f"• Date/heure: {start_datetime.strftime('%d/%m/%Y %H:%M')}")
            st.write(f"• Points météo: {weather_data['data_points']}")
            st.write(f"• Type parcours: {geometry_analysis['type']}")
    
    # Export des données
    report_data = {
        'metadata': {
            'fichier_gpx': uploaded_file.name,
            'date_analyse': datetime.now().isoformat(),
            'date_heure_depart': start_datetime.isoformat(),
            'vitesse_moyenne_kmh': avg_speed,
            'distance_totale_km': round(total_distance/1000, 2),
            'duree_estimee_minutes': round(total_distance/1000/avg_speed*60, 0)
        },
        'geometrie': {
            'type': geometry_analysis['type'],
            'distance_fermeture_m': geometry_analysis.get('loop_closure_distance', 0),
            'direction_principale': geometry_analysis.get('loop_direction') or 
                                  geometry_analysis.get('main_direction', {}).get('cardinal', 'indetermine'),
            'nomenclature': nomenclature
        },
        'coordonnees': {
            'centre_trace_gps': weather_data['center_coordinates'],
            'centre_openmeteo': weather_data['actual_coordinates'],
            'altitude_m': weather_data['elevation'],
            'fuseau_horaire': weather_data['timezone'],
            'points_meteo': weather_data['data_points']
        },
        'analyse_comparative': {
            'sense_a': {
                'nom': nomenclature['sense_a']['name'],
                'description': nomenclature['sense_a']['description'],
                'score_favorabilite': analysis_results['scores']['sense_a'],
                'statistiques': analysis_results['detailed_stats']['sense_a']
            },
            'sense_b': {
                'nom': nomenclature['sense_b']['name'],
                'description': nomenclature['sense_b']['description'],
                'score_favorabilite': analysis_results['scores']['sense_b'],
                'statistiques': analysis_results['detailed_stats']['sense_b']
            }
        },
        'recommandation': {
            'sens_optimal': analysis_results['recommendation'],
            'niveau_avantage': recommendation_level,
            'difference_score_pourcent': score_diff,
            'justification': f"Analyse {geometry_analysis['type']} avec données Open-Meteo"
        }
    }
    
    # Boutons d'export
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            label="📊 Rapport JSON complet",
            data=json.dumps(report_data, indent=2, ensure_ascii=False),
            file_name=f"rapport_cycliste_{uploaded_file.name.replace('.gpx', '')}_{start_datetime.strftime('%Y%m%d_%H%M')}.json",
            mime="application/json"
        )
    
    with col2:
        # Rapport texte simplifié
        rapport_texte = f"""
RAPPORT D'OPTIMISATION CYCLISTE
===============================

📁 Fichier: {uploaded_file.name}
📅 Date d'analyse: {datetime.now().strftime('%d/%m/%Y %H:%M')}
🚴 Départ prévu: {start_datetime.strftime('%d/%m/%Y %H:%M')}

PARCOURS
--------
🗺️ Type: {geometry_analysis['type']}
📏 Distance: {total_distance/1000:.1f} km
⏱️ Durée estimée: {total_distance/1000/avg_speed*60:.0f} minutes
🎯 Vitesse: {avg_speed} km/h

ANALYSE COMPARATIVE
------------------
{nomenclature['sense_a']['emoji']} {nomenclature['sense_a']['name']}:
   • Score: {analysis_results['scores']['sense_a']:+.1f}%
   • Vent de face: {analysis_results['detailed_stats']['sense_a']['face_km']:.1f} km
   • Vent de dos: {analysis_results['detailed_stats']['sense_a']['dos_km']:.1f} km

{nomenclature['sense_b']['emoji']} {nomenclature['sense_b']['name']}:
   • Score: {analysis_results['scores']['sense_b']:+.1f}%
   • Vent de face: {analysis_results['detailed_stats']['sense_b']['face_km']:.1f} km
   • Vent de dos: {analysis_results['detailed_stats']['sense_b']['dos_km']:.1f} km

RECOMMANDATION
--------------
{recommendation_icon} {analysis_results['recommendation']}
Différence: {abs(score_diff):.1f}% ({recommendation_level})

---
Généré par RideFlow - Optimiseur Cycliste
        """
        
        st.download_button(
            label="📄 Rapport TXT simple",
            data=rapport_texte,
            file_name=f"rapport_simple_{uploaded_file.name.replace('.gpx', '')}_{start_datetime.strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )
    
    with col3:
        # Export CSV des segments
        if 'sense_a' in analysis_results:
            segments_df = pd.DataFrame(analysis_results['sense_a'])
            csv_data = segments_df.to_csv(index=False, encoding='utf-8')
            
            st.download_button(
                label="📈 Données CSV",
                data=csv_data,
                file_name=f"segments_analyse_{uploaded_file.name.replace('.gpx', '')}.csv",
                mime="text/csv"
            )

def main():
    st.title("🚴 Optimiseur de Parcours Cycliste 🌪️")
    st.markdown("""
    Trouvez le meilleur sens de parcours en fonction du vent avec **Open-Meteo** !
    
    🎯 **Fonctionnalités avancées:**
    - Détection automatique du type de parcours (boucle/linéaire)
    - Nomenclature intelligente des sens de parcours
    - Analyse météorologique complète avec Open-Meteo
    - Recommandations contextuelles et cartes interactives
    """)
    
    optimizer = WindOptimizer()
    
    # Affichage des limites de l'API gratuite
    today, max_date = optimizer.get_forecast_date_limits()
    st.info(f"📅 **API gratuite Open-Meteo:** Prévisions disponibles jusqu'au {max_date} "
           f"({optimizer.max_forecast_days} jours maximum)")
    
    # Sidebar pour les paramètres
    st.sidebar.header("⚙️ Configuration")
    
    # Vitesse moyenne du cycliste
    avg_speed = st.sidebar.slider("Vitesse moyenne (km/h)", 15, 40, 25, 
                                 help="Vitesse moyenne prévue pour estimer les horaires de passage")
    
    # Date et heure de départ avec limites
    st.sidebar.write("📅 **Date et heure de départ**")
    start_date = st.sidebar.date_input(
        "Date de départ", 
        datetime.now().date(),
        min_value=today - timedelta(days=30),  # 30 jours d'historique
        max_value=max_date,
        help=f"Limites: historique 30 jours, prévisions jusqu'au {max_date}"
    )
    
    start_time = st.sidebar.time_input("Heure de départ", datetime.now().time())
    
    # Conversion en datetime avec fuseau horaire français
    start_datetime = optimizer.timezone.localize(datetime.combine(start_date, start_time))
    
    # Affichage de la date/heure sélectionnée
    st.sidebar.success(f"🕐 Départ prévu: {start_datetime.strftime('%d/%m/%Y à %H:%M')} (heure française)")
    
    # Options avancées
    with st.sidebar.expander("🔧 Options avancées"):
        show_detailed_weather = st.checkbox("Afficher météo détaillée", True)
        show_wind_analysis = st.checkbox("Analyse des vents dominants", True)
        export_format = st.selectbox("Format d'export préféré", 
                                   ["JSON complet", "Rapport simple", "Données CSV"])
    
    # Upload du fichier GPX
    st.sidebar.header("📁 Import GPX")
    uploaded_file = st.sidebar.file_uploader("Choisir un fichier GPX", type="gpx",
                                            help="Fichier de trace GPS au format GPX")
    
    
    if uploaded_file:
        # Parse du GPX
        with st.spinner("📄 Analyse du fichier GPX..."):
            points = optimizer.parse_gpx(uploaded_file)
            
        if points:
            st.success(f"✅ Fichier GPX chargé: {len(points)} points GPS")
            
            # Calcul du centre et des limites
            center, bounds = optimizer.get_gpx_center_and_bounds(points)
            
            # Affichage des informations GPS
            col1, col2, col3 = st.columns(3)
            col1.metric("📍 Points GPS", f"{len(points):,}")
            
            if center:
                col2.metric("🌍 Centre Latitude", f"{center['lat']:.6f}°")
                col3.metric("🌍 Centre Longitude", f"{center['lon']:.6f}°")
            
            # Analyse géométrique intelligente
            with st.spinner("🔍 Analyse géométrique intelligente..."):
                geometry_analysis = optimizer.analyze_route_geometry(points)
                
            # Affichage des informations géométriques
            st.subheader("🎯 Analyse géométrique intelligente")
            
            if geometry_analysis['type'] == 'loop':
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("🔄 Type", "Boucle fermée")
                with col2:
                    st.metric("↩️ Sens détecté", geometry_analysis['loop_direction'].title())
                with col3:
                    st.metric("📏 Distance fermeture", f"{geometry_analysis['loop_closure_distance']:.0f} m")
                with col4:
                    st.metric("🎯 Circularité", f"{(1-geometry_analysis['closure_ratio'])*100:.0f}%")
                
                st.success(f"✅ Boucle {geometry_analysis['loop_direction']} détectée - "
                        f"Fermeture optimale de {geometry_analysis['loop_closure_distance']:.0f}m")
                
            elif geometry_analysis['type'] == 'linear':
                direction = geometry_analysis['main_direction']
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("📍 Type", "Trajet linéaire")
                with col2:
                    st.metric("🧭 Direction", f"{direction['emoji']} {direction['cardinal']}")
                with col3:
                    st.metric("📏 Distance directe", f"{direction['distance_km']:.1f} km")
                with col4:
                    st.metric("🧭 Cap", f"{direction['bearing']:.0f}°")
                
                st.info(f"🧭 Trajet linéaire vers le {direction['cardinal']} "
                    f"({direction['bearing']:.0f}° - {direction['distance_km']:.1f}km à vol d'oiseau)")
            
            # Génération de la nomenclature claire
            nomenclature = optimizer.generate_route_nomenclature(geometry_analysis)
            
            st.subheader("🏷️ Nomenclature intelligente des parcours")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"""
                {nomenclature['sense_a']['emoji']} **{nomenclature['sense_a']['name']}**
                
                {nomenclature['sense_a']['description']}
                
                ℹ️ {nomenclature['sense_a']['detail']}
                """)
            with col2:
                st.info(f"""
                {nomenclature['sense_b']['emoji']} **{nomenclature['sense_b']['name']}**
                
                {nomenclature['sense_b']['description']}
                
                ℹ️ {nomenclature['sense_b']['detail']}
                """)
            
            # Calcul des segments
            segments, total_distance = optimizer.calculate_distance_and_bearing(points)
            
            # Métriques du parcours
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📏 Distance totale", f"{total_distance/1000:.2f} km")
            col2.metric("⏱️ Temps estimé", f"{total_distance/1000/avg_speed*60:.0f} min")
            col3.metric("🚴 Vitesse", f"{avg_speed} km/h")
            col4.metric("📊 Segments", f"{len(segments)}")
            
            # Bouton d'analyse automatique principal
            if st.button("🌪️ ANALYSER LE VENT AUTOMATIQUEMENT", type="primary", use_container_width=True):
                with st.spinner("📡 Récupération des données météorologiques..."):
                    
                    # Envoi automatique des coordonnées centrales
                    weather = optimizer.get_weather_data(center, start_datetime)
                
                if weather:
                    st.success("✅ Données météorologiques récupérées avec succès!")
                    
                    # Informations de géolocalisation météo
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📍 Lat. demandée", f"{weather['center_coordinates']['lat']:.6f}°")
                    with col2:
                        st.metric("📍 Lon. demandée", f"{weather['center_coordinates']['lon']:.6f}°")
                    with col3:
                        st.metric("🎯 Lat. Open-Meteo", f"{weather['actual_coordinates']['lat']:.6f}°")
                    with col4:
                        st.metric("🎯 Lon. Open-Meteo", f"{weather['actual_coordinates']['lon']:.6f}°")
                    
                    # Métadonnées météo
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("⛰️ Altitude", f"{weather['elevation']:.0f} m")
                    with col2:
                        st.metric("📊 Points de données", f"{weather['data_points']}")
                    with col3:
                        st.metric("🕐 Fuseau horaire", weather['timezone'])
                    
                    # Widget résumé géométrique
                    create_enhanced_summary_widget(geometry_analysis, nomenclature)
                    
                    # Analyse complète avec la nouvelle nomenclature
                    analysis_results = display_enhanced_analysis_results(
                        optimizer, segments, weather, avg_speed, start_datetime,
                        geometry_analysis, nomenclature, total_distance
                    )
                    
                    # Génération du rapport complet
                    generate_comprehensive_report(
                        geometry_analysis, nomenclature, analysis_results,
                        weather, total_distance, avg_speed, start_datetime, uploaded_file
                    )
    else:
        st.info("📁 Uploadez un fichier GPX pour commencer l'analyse.")

    def main():
        st.title("🚴 Optimiseur de Parcours Cycliste 🌪️")
        st.markdown("Trouvez le meilleur sens de parcours en fonction du vent avec **Open-Meteo** !")
        
        optimizer = WindOptimizer()
        
        # Sidebar pour les paramètres
        st.sidebar.header("⚙️ Configuration")
        
        # Vitesse moyenne du cycliste
        avg_speed = st.sidebar.slider("Vitesse moyenne (km/h)", 15, 40, 25)
        
        # Heure de départ
        start_time = st.sidebar.time_input("Heure de départ", datetime.now().time())
        start_date = st.sidebar.date_input("Date de départ", datetime.now().date())
        start_datetime = datetime.combine(start_date, start_time)
        
        # Upload du fichier GPX
        st.sidebar.header("📁 Import GPX")
        uploaded_file = st.sidebar.file_uploader("Choisir un fichier GPX", type="gpx")
        
        if uploaded_file:
            # Parse du GPX
            with st.spinner("Analyse du fichier GPX..."):
                points = optimizer.parse_gpx(uploaded_file)
                
            if points:
                st.success(f"✅ Fichier GPX chargé: {len(points)} points")
                
                # Calcul des segments
                segments, total_distance = optimizer.calculate_distance_and_bearing(points)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Points GPS", len(points))
                col2.metric("Distance totale", f"{total_distance/1000:.2f} km")
                col3.metric("Temps estimé", f"{total_distance/1000/avg_speed*60:.0f} min")
                
                # Récupération des données météo
                if st.button("🌡️ Analyser le vent", type="primary"):
                    with st.spinner("Récupération des données météo Open-Meteo..."):
                        # Utilise le point central pour la météo
                        center_lat = np.mean([p['lat'] for p in points])
                        center_lon = np.mean([p['lon'] for p in points])
                        center_coords = {'lat': center_lat, 'lon': center_lon}
                        
                        weather = optimizer.get_weather_data(center_coords, start_datetime)
                    
                    if weather:
                        st.success("✅ Données météo récupérées!")
                        
                        # Affichage des infos météo
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Lat. Demandée", f"{weather['center_coordinates']['lat']:.4f}°") 
                        with col2:
                            st.metric("Lon. Demandée", f"{weather['center_coordinates']['lon']:.4f}°")
                        with col3:
                            st.metric("Lat. Open-Meteo", f"{weather['actual_coordinates']['lat']:.4f}°")
                        with col4:
                            st.metric("Lon. Open-Meteo", f"{weather['actual_coordinates']['lon']:.4f}°")
                        
                        # Analyse dans les deux sens
                        st.header("📊 Analyse comparative")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("🔄 Sens original")
                            original_analysis = optimizer.analyze_wind_impact_temporal(
                                segments, weather, avg_speed, start_datetime
                            )
                            
                            # Statistiques
                            face_distance = sum(s['distance'] for s in original_analysis if s['wind_type'] == 'face')
                            dos_distance = sum(s['distance'] for s in original_analysis if s['wind_type'] == 'dos')
                            lateral_distance = sum(s['distance'] for s in original_analysis if s['wind_type'] == 'lateral')
                            
                            avg_wind_speed = np.mean([s['wind_speed'] for s in original_analysis])
                            
                            st.metric("Vent de face", f"{face_distance/1000:.2f} km ({face_distance/total_distance*100:.1f}%)")
                            st.metric("Vent de dos", f"{dos_distance/1000:.2f} km ({dos_distance/total_distance*100:.1f}%)")
                            st.metric("Vent latéral", f"{lateral_distance/1000:.2f} km ({lateral_distance/total_distance*100:.1f}%)")
                            st.metric("Vent moyen", f"{avg_wind_speed:.1f} km/h")
                            
                            # Carte
                            map_original = optimizer.create_enhanced_map(original_analysis, "Sens original")
                            if map_original:
                                folium_static(map_original)
                        
                        with col2:
                            st.subheader("🔄 Sens inverse")
                            reversed_segments = optimizer.reverse_segments(segments)
                            reverse_analysis = optimizer.analyze_wind_impact_temporal(
                                reversed_segments, weather, avg_speed, start_datetime
                            )
                            
                            # Statistiques
                            face_distance_rev = sum(s['distance'] for s in reverse_analysis if s['wind_type'] == 'face')
                            dos_distance_rev = sum(s['distance'] for s in reverse_analysis if s['wind_type'] == 'dos')
                            lateral_distance_rev = sum(s['distance'] for s in reverse_analysis if s['wind_type'] == 'lateral')
                            
                            avg_wind_speed_rev = np.mean([s['wind_speed'] for s in reverse_analysis])
                            
                            st.metric("Vent de face", f"{face_distance_rev/1000:.2f} km ({face_distance_rev/total_distance*100:.1f}%)")
                            st.metric("Vent de dos", f"{dos_distance_rev/1000:.2f} km ({dos_distance_rev/total_distance*100:.1f}%)")
                            st.metric("Vent latéral", f"{lateral_distance_rev/1000:.2f} km ({lateral_distance_rev/total_distance*100:.1f}%)")
                            st.metric("Vent moyen", f"{avg_wind_speed_rev:.1f} km/h")
                            
                            # Carte
                            map_reverse = optimizer.create_enhanced_map(reverse_analysis, "Sens inverse")
                            if map_reverse:
                                folium_static(map_reverse)
                        
                        # Graphique des prévisions météo
                        st.header("�� Évolution des conditions météo")
                        
                        # Prépare les données pour le graphique
                        weather_df = weather['hourly_data'].copy()
                        weather_df['hour'] = weather_df['date'].dt.hour
                        weather_df_today = weather_df[weather_df['date'].dt.date == start_date]
                        
                        if len(weather_df_today) > 0:
                            fig_weather = px.line(weather_df_today, x='hour', 
                                                y=['wind_speed_10m', 'wind_speed_80m'], 
                                                title="Évolution du vent dans la journée",
                                                labels={'value': 'Vitesse (km/h)', 'hour': 'Heure'})
                            st.plotly_chart(fig_weather, use_container_width=True)
                        
                        # Graphique comparatif final
                        comparison_data = {
                            'Sens': ['Original', 'Inverse'],
                            'Vent de face (km)': [face_distance/1000, face_distance_rev/1000],
                            'Vent de dos (km)': [dos_distance/1000, dos_distance_rev/1000],
                            'Vent latéral (km)': [lateral_distance/1000, lateral_distance_rev/1000]
                        }
                        
                        df = pd.DataFrame(comparison_data)
                        
                        fig = px.bar(df, x='Sens', 
                                y=['Vent de face (km)', 'Vent de dos (km)', 'Vent latéral (km)'],
                                title="Comparaison des conditions de vent",
                                color_discrete_map={
                                    'Vent de face (km)': 'red',
                                    'Vent de dos (km)': 'green',
                                    'Vent latéral (km)': 'orange'
                                })
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Recommandation
                        st.header("🏆 Recommandation")
                        
                        # Score basé sur la différence vent de dos - vent de face
                        score_original = dos_distance - face_distance
                        score_reverse = dos_distance_rev - face_distance_rev
                        
                        if score_original > score_reverse:
                            st.success("🎯 **Recommandation: Parcours dans le sens ORIGINAL**")
                            st.write(f"Avantage: {(score_original - score_reverse)/1000:.2f} km de vent plus favorable")
                        elif score_reverse > score_original:
                            st.success("🎯 **Recommandation: Parcours dans le sens INVERSE**")
                            st.write(f"Avantage: {(score_reverse - score_original)/1000:.2f} km de vent plus favorable")
                        else:
                            st.info("🤝 **Les deux sens sont équivalents**")
                        
                        # Détails temporels
                        with st.expander("📍 Détails par segment"):
                            st.subheader("Sens original")
                            segments_df = pd.DataFrame([{
                                'Segment': i+1,
                                'Distance (m)': s['distance'],
                                'Heure': s['time'],
                                'Vent': s['wind_type'],
                                'Vitesse vent (km/h)': f"{s['wind_speed']:.1f}",
                                'Impact': f"{s['wind_impact']:.1f}",
                                'Température (°C)': f"{s['temperature']:.1f}"
                            } for i, s in enumerate(original_analysis[:10])])  # Limite à 10 pour l'affichage
                            st.dataframe(segments_df, use_container_width=True)
                        
                        # Export des résultats
                        st.header("📄 Export des résultats")
                        
                        report_data = {
                            'parcours': uploaded_file.name,
                            'date_heure_depart': start_datetime.isoformat(),
                            'vitesse_moyenne_kmh': avg_speed,
                            'distance_totale_km': round(total_distance/1000, 2),
                            'coordonnees_centre': {
                                'lat': weather['coordinates']['lat'],
                                'lon': weather['coordinates']['lon']
                            },
                            'elevation_m': weather['elevation'],
                            'sens_original': {
                                'vent_face_km': round(face_distance/1000, 2),
                                'vent_dos_km': round(dos_distance/1000, 2),
                                'vent_lateral_km': round(lateral_distance/1000, 2),
                                'vent_moyen_kmh': round(avg_wind_speed, 1),
                                'score': round(score_original/1000, 2)
                            },
                            'sens_inverse': {
                                'vent_face_km': round(face_distance_rev/1000, 2),
                                'vent_dos_km': round(dos_distance_rev/1000, 2),
                                'vent_lateral_km': round(lateral_distance_rev/1000, 2),
                                'vent_moyen_kmh': round(avg_wind_speed_rev, 1),
                                'score': round(score_reverse/1000, 2)
                            },
                            'recommandation': 'original' if score_original > score_reverse else 'inverse' if score_reverse > score_original else 'equivalent',
                            'avantage_km': abs(score_original - score_reverse)/1000
                        }
                        
                        st.download_button(
                            label="📊 Télécharger le rapport JSON",
                            data=json.dumps(report_data, indent=2, ensure_ascii=False),
                            file_name=f"analyse_vent_{uploaded_file.name.replace('.gpx', '').replace(' ', '_')}_{start_date.strftime('%Y%m%d')}.json",
                            mime="application/json"
                        )
        
        else:
            st.info("📁 Uploadez un fichier GPX pour commencer l'analyse.")
if __name__ == "__main__":
    main()
