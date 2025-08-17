# 🚴‍♂️ RideFlow - Optimiseur de Parcours Cyclistes

**Optimisez vos parcours cyclistes avec l'intelligence météorologique évolutive ! 🚴‍♂️💨**

RideFlow est une application web complète qui analyse vos parcours cyclistes GPX et recommande la meilleure direction à emprunter en fonction de l'évolution des conditions de vent au cours du temps.

<img width="2780" height="4694" alt="Image" src="https://github.com/user-attachments/assets/2d2d41b7-1694-41c7-8f3c-2c28296dde03" />

## ✨ Fonctionnalités Principales

### 🎯 Analyse Intelligente Évolutive
- **Parse GPX Robuste** : Analyse complète avec support tracks/routes/waypoints
- **Météo Temporelle** : Analyse l'évolution du vent segment par segment dans le temps
- **Calculs Géodésiques Précis** : Distances, orientations et temps de parcours optimisés
- **Analyse Bidirectionnelle** : Compare les deux sens avec impact temporel réel
- **Simplification Intelligente** : Optimisation automatique pour les gros fichiers GPX (>200 points)

### 🌬️ Modélisation Météorologique Avancée
- **Évolution Temporelle** : Prend en compte le changement de vent pendant le parcours
- **API Open-Meteo** : Données horaires sur 3 jours (passé/présent/futur)
- **Prévisions Précises** : Vent à 10m, direction et vitesse par segment
- **Impact Dynamique** : Calcul en temps réel de l'impact vent/performance

### 🗺️ Visualisation Interactive Enrichie
- **Carte Leaflet Avancée** : Segments colorés selon l'impact du vent évolutif
- **Indicateur de Vent Central** : Flèche rotative avec vent dominant
- **Popups Détaillés** : Informations complètes par segment (temps, vent, impact)
- **Interactivité Améliorée** : Effets hover et animations sur les segments
- **Gestion Boucles/Linéaire** : Détection automatique du type de parcours

### 📊 Analyses et Graphiques Enrichis
- **Rose des Vents Évolutive** : Distribution du vent sur la durée totale
- **Comparaison Temporelle** : Graphique temps de parcours par direction
- **Tableau Groupé** : Analyse par groupes de segments avec statistiques
- **Recommandations Intelligentes** : Conseils personnalisés selon l'économie de temps
- **Statistiques Avancées** : Distance de vent de face, segments favorables, etc.

### 🎨 Interface Moderne et Responsive
- **Design Bootstrap 5** : Interface professionnelle et moderne
- **Responsive Total** : Adapté mobile, tablette et desktop
- **Animations Fluides** : Chargements et transitions élégants
- **Feedback Utilisateur** : Messages d'erreur et confirmations clairs
- **Légende Interactive** : Compréhension immédiate des codes couleurs

## 📁 Structure du Projet

```
rideflow/
├── index.php              # Interface utilisateur principale
├── functions.php           # API backend et logique métier
├── assets/
│   ├── style.css          # Styles personnalisés
│   └── app.js             # JavaScript principal
├── docker/
│   └── apache.conf        # Configuration Apache
├── uploads/               # Dossier des fichiers GPX uploadés
├── cache/                 # Cache des données météo
├── logs/                  # Logs Apache
├── Dockerfile             # Image Docker
├── docker-compose.yml     # Orchestration Docker
├── portainer-stack.yml    # Stack Portainer pour Synology
├── .htaccess             # Configuration sécurité Apache
└── README.md             # Cette documentation
```

## 🚀 Installation et Déploiement

### Prérequis
- **Docker & Docker Compose** : Version récente
- **2GB RAM minimum** : Pour traitement des gros GPX
- **Connexion Internet** : Pour API météorologique
- **Port 8080 libre** : Ou autre port configuré

## Installation Rapide

### Sur Synology

```bash
1. Remplacer les fichiers dans `/volume1/docker/rideflow/`
2. docker build -t rideflow-app .
3. Déployer le stack
3 bis Si déjà déployé pour mettre à jour Portainer → Stack rideflow → container → Re-deploy (sans option pull)
```

### En local

```bash
# Démarrer le docker
docker compose up --build

# Stopper le docker
docker compose down

# Accéder à l'application
open http://localhost:8080
```

## 📋 Utilisation

### 1. **Upload GPX**
- Glissez-déposez votre fichier `.gpx`
- Validation automatique et extraction des données
- Affichage des informations : distance, points, type de parcours

### 2. **Configuration Temporelle**
- **Date/Heure** : Moment prévu du départ
- **Vitesse Cycliste** : Votre vitesse moyenne prévue (km/h)
- Calcul automatique de l'évolution temporelle

### 3. **Analyse Météorologique**
- Clic sur "Analyser les Conditions de Vent"
- Récupération des données météo en temps réel
- Calcul de l'impact pour chaque segment dans le temps

### 4. **Résultats Détaillés**
- **Carte Colorée** : Segments selon impact du vent
- **Recommandation** : Meilleur sens avec économie de temps
- **Graphiques** : Rose des vents et comparaison temporelle
- **Tableau** : Détails par groupe de segments

### ⏱️ **Analyse Temporelle Évolutive**
- Calcul segment par segment de l'heure d'arrivée
- Adaptation aux conditions de vent changeantes
- Précision horaire sur les prévisions météo

### 🔄 **Optimisations Performances**
- Simplification intelligente des tracés complexes
- Cache des données météorologiques
- Gestion mémoire optimisée pour gros fichiers

### 📊 **Analyses Enrichies**
- Groupement intelligent des segments (par 20)
- Statistiques avancées (distance vent de face, temps par direction)
- Conseils personnalisés selon l'économie potentielle

### 🎨 **Interface **
- Indicateurs de vent avec rotation dynamique
- Popups enrichis avec toutes les métriques

## 📈 Algorithmes et Précision

### Calcul d'Impact du Vent
```
Impact = f(angle_relatif, vitesse_vent, vitesse_cycliste, temps)

- Vent de face (0-30°) : +5% à +40% du temps
- Vent de côté (30-120°) : +2% à +12% du temps  
- Vent arrière (150-180°) : -5% à -32% du temps
```

### Précision Géodésique
- **Distance** : Formule de Vincenty (précision métrique)
- **Orientation** : Calcul spherique exact
- **Temps** : Intégration vitesse + impact vent

## 🔧 Configuration

### Paramètres Météo
- **Prévisions** : 3 jours (passé/futur)
- **Résolution** : Données horaires
- **Source** : Open-Meteo (gratuit, fiable)
- **Timeout** : 15 secondes max par requête

## 🚧 Limitations Connues

- **Fichiers GPX** : Maximum ~1000 segments (simplification auto)
- **Prévisions** : Limitées à ±3 jours autour de la date choisie
- **Vent Local** : Pas de prise en compte micro-climatique
- **Relief** : Impact du dénivelé non intégré

---

**RideFlow v2.1** - *Optimisez chaque coup de pédale avec l'intelligence météorologique ! 🚴‍♂️⚡*
