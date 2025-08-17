<?php
session_start();
error_log("RideFlow v2.1 - Index loaded at " . date('Y-m-d H:i:s'));
?>
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RideFlow - Optimiseur de Parcours Cyclistes</title>
    
    <!-- CSS Dependencies -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="assets/style.css">
    
    <!-- Favicon -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><text y='20' font-size='20'>🚴</text></svg>">
    
    <!-- Meta tags pour SEO -->
    <meta name="description" content="Optimisez vos parcours cyclistes selon les conditions de vent. Analysez vos fichiers GPX et trouvez le meilleur sens de parcours.">
    <meta name="keywords" content="cyclisme, vent, GPX, parcours, optimisation, météo">
    <meta name="author" content="RideFlow">
</head>

<body class="bg-light">
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">
                <i class="bi bi-bicycle"></i> RideFlow
            </a>
            <span class="navbar-text text-light">
                Optimiseur de parcours cyclistes basé sur les conditions de vent
            </span>
        </div>
    </nav>
    
    <div class="container-fluid mt-3">
        <div class="row">
            <!-- COLONNE GAUCHE: Configuration -->
            <div class="col-lg-3 col-md-4 mb-4">
                <div class="card shadow-sm">
                    <div class="card-header bg-secondary text-white">
                        <h5 class="mb-0">
                            <i class="bi bi-gear-fill"></i> Configuration
                        </h5>
                    </div>
                    <div class="card-body">
                        <form id="gpxForm" enctype="multipart/form-data">
                            <!-- Upload GPX -->
                            <div class="mb-4">
                                <label for="gpx-file" class="form-label fw-bold">
                                    <i class="bi bi-file-earmark-arrow-up"></i> Fichier GPX
                                </label>
                                <input type="file" 
                                       class="form-control" 
                                       id="gpx-file" 
                                       name="gpx" 
                                       accept=".gpx"
                                       aria-describedby="gpx-help" />
                                <div id="gpx-help" class="form-text">
                                    Sélectionnez votre parcours GPX
                                </div>
                            </div>
                            
                            <!-- Date et Heure -->
                            <div class="mb-4">
                                <label for="ride-datetime" class="form-label fw-bold">
                                    <i class="bi bi-calendar-event"></i> Date et Heure
                                </label>
                                <input type="datetime-local" 
                                       class="form-control" 
                                       id="ride-datetime" 
                                       name="datetime"
                                       aria-describedby="datetime-help" />
                                <div id="datetime-help" class="form-text">
                                    Prévision météo pour cette période
                                </div>
                            </div>
                            
                            <!-- Vitesse -->
                            <div class="mb-4">
                                <label for="rider-speed" class="form-label fw-bold">
                                    <i class="bi bi-speedometer2"></i> Vitesse moyenne (km/h)
                                </label>
                                <input type="number" 
                                       class="form-control" 
                                       id="rider-speed" 
                                       name="rider_speed" 
                                       value="25" 
                                       min="10" 
                                       max="60" 
                                       step="0.1"
                                       aria-describedby="speed-help" />
                                <div id="speed-help" class="form-text">
                                    Votre vitesse de croisière habituelle
                                </div>
                            </div>
                            
                            <!-- Boutons d'action -->
                            <button id="analyze-btn" 
                                    class="btn btn-success w-100 mb-2" 
                                    type="button" 
                                    disabled
                                    aria-describedby="analyze-help">
                                <i class="bi bi-cloud-snow"></i> Analyser les Conditions de Vent
                                <small class="d-block mt-1 opacity-75">
                                    ⚠️ Utilise l'API météo
                                </small>
                            </button>
                            
                            <button id="clear-btn" 
                                    class="btn btn-outline-secondary w-100" 
                                    type="button">
                                <i class="bi bi-trash"></i> Effacer Tout
                            </button>
                        </form>
                        
                        <!-- Informations GPX chargé -->
                        <div id="gpx-info" class="mt-3" style="display: none;">
                            <div class="alert alert-info mb-0">
                                <small>
                                    <strong><i class="bi bi-check-circle-fill"></i> Parcours chargé:</strong><br>
                                    <div class="mt-2">
                                        <i class="bi bi-file-text"></i> <strong>Nom:</strong> 
                                        <span id="gpx-name" class="text-primary">-</span><br>
                                        <i class="bi bi-rulers"></i> <strong>Distance:</strong> 
                                        <span id="gpx-distance" class="text-success">-</span> km<br>
                                        <i class="bi bi-geo-alt"></i> <strong>Points:</strong> 
                                        <span id="gpx-points" class="text-info">-</span>
                                    </div>
                                </small>
                            </div>
                        </div>

                        <!-- Informations API -->
                        <div class="alert alert-warning mt-3" role="alert">
                            <small>
                                <i class="bi bi-info-circle-fill"></i> 
                                <strong>Information:</strong><br>
                                L'analyse météorologique utilise l'API gratuite 
                                <a href="https://open-meteo.com" target="_blank" rel="noopener" class="alert-link">Open-Meteo</a>. 
                                Cliquez sur "Analyser" uniquement quand vous êtes prêt.
                            </small>
                        </div>
                    </div>
                </div>
                
                <!-- Légende des couleurs -->
                <div class="card shadow-sm mt-3" id="legend-card" style="display: none;">
                    <div class="card-header bg-info text-white">
                        <h6 class="mb-0">
                            <i class="bi bi-info-circle-fill"></i> Légende
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <strong>Tracé du parcours :</strong>
                            <div class="d-flex align-items-center mb-2 mt-2">
                                <div class="legend-line me-2" style="background-color: #28a745;"></div>
                                <small>Segments favorables (vent arrière)</small>
                            </div>
                            <div class="d-flex align-items-center mb-2">
                                <div class="legend-line me-2" style="background-color: #dc3545;"></div>
                                <small>Segments défavorables (vent de face)</small>
                            </div>
                            <div class="d-flex align-items-center mb-2">
                                <div class="legend-line me-2" style="background-color: #ffc107;"></div>
                                <small>Segments avec vent de travers</small>
                            </div>
                            <div class="d-flex align-items-center mb-2">
                                <div class="legend-line me-2" style="background-color: #6c757d;"></div>
                                <small>Segments mixtes/indéterminés</small>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <strong>Marqueurs :</strong>
                            <div class="d-flex align-items-center mb-2 mt-2">
                                <div class="legend-circle me-2" style="background-color: lightgreen; border: 2px solid green;"></div>
                                <small>Point de départ</small>
                            </div>
                            <div class="d-flex align-items-center mb-2">
                                <div class="legend-circle me-2" style="background-color: lightcoral; border: 2px solid red;"></div>
                                <small>Point d'arrivée</small>
                            </div>
                            <div class="d-flex align-items-center mb-2">
                                <div class="wind-arrow-legend me-2">🧭</div>
                                <small>Indicateur de vent dominant</small>
                            </div>
                        </div>
                        
                        <div class="alert alert-light mb-0">
                            <small>
                                <strong>💡 Astuce :</strong> Cliquez sur les segments colorés 
                                du tracé pour voir les détails de l'impact du vent.
                            </small>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- COLONNE DROITE: Résultats et Carte -->
            <div class="col-lg-9 col-md-8">
                
                <!-- Spinner de chargement -->
                <div id="loading-spinner" class="text-center py-5" style="display: none;">
                    <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Chargement...</span>
                    </div>
                    <div class="mt-3">
                        <h5>Analyse en cours...</h5>
                        <p class="text-muted mb-0">Récupération des données météorologiques...</p>
                    </div>
                </div>
                
                <!-- Section des Résultats -->
                <div id="results-section" style="display: none;">
                    <!-- Recommandations -->
                    <div class="row mb-4">
                        <div class="col-12">
                            <div class="card shadow-sm">
                                <div class="card-header bg-success text-white">
                                    <h5 class="mb-0">
                                        <i class="bi bi-check-circle-fill"></i> Recommandations Météorologiques
                                    </h5>
                                </div>
                                <div class="card-body">
                                    <div id="recommendations-content">
                                        <!-- Contenu généré par JavaScript -->
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Carte -->
                    <div class="row mb-4">
                        <div class="col-12">
                            <div class="card shadow-sm map-card">
                                <div class="card-header bg-primary text-white">
                                    <h5 class="mb-0">
                                        <i class="bi bi-geo-alt-fill"></i> Visualisation du Parcours
                                    </h5>
                                </div>
                                <div id="map" aria-label="Carte interactive du parcours cycliste"></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Graphiques -->
                    <div class="row mb-4">
                        <div class="col-lg-6 mb-3">
                            <div class="card shadow-sm">
                                <div class="card-header bg-warning text-dark">
                                    <h6 class="mb-0">
                                        <i class="bi bi-compass"></i> Rose des Vents
                                    </h6>
                                </div>
                                <div class="card-body text-center">
                                    <div class="chart-container">
                                        <canvas id="wind-rose-chart" 
                                                aria-label="Graphique en rose des vents montrant la distribution des directions de vent"></canvas>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-lg-6 mb-3">
                            <div class="card shadow-sm">
                                <div class="card-header bg-warning text-dark">
                                    <h6 class="mb-0">
                                        <i class="bi bi-graph-up-arrow"></i> Comparaison des Temps
                                    </h6>
                                </div>
                                <div class="card-body text-center">
                                    <div class="chart-container">
                                        <canvas id="wind-impact-chart" 
                                                aria-label="Graphique comparant les temps de parcours selon le sens"></canvas>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Tableau des segments -->
                    <div class="row">
                        <div class="col-12">
                            <div class="card shadow-sm">
                                <div class="card-header bg-dark text-white">
                                    <h5 class="mb-0">
                                        <i class="bi bi-table"></i> Analyse Détaillée par Segments
                                    </h5>
                                </div>
                                <div class="card-body">
                                    <div class="alert alert-info mb-3">
                                        <i class="bi bi-lightbulb-fill"></i> 
                                        <strong>Lecture du tableau:</strong> 
                                        Ce tableau présente un résumé par zones du parcours. 
                                        Les zones favorables indiquent un vent arrière, 
                                        les défavorables un vent de face.
                                    </div>
                                    <div class="table-responsive">
                                        <table id="segments-table" class="table table-striped table-hover">
                                            <thead class="table-dark">
                                                <tr>
                                                    <th scope="col">
                                                        <i class="bi bi-geo"></i> Segment
                                                    </th>
                                                    <th scope="col">
                                                        <i class="bi bi-rulers"></i> Distance
                                                    </th>
                                                    <th scope="col">
                                                        <i class="bi bi-compass"></i> Direction Parcours
                                                    </th>
                                                    <th scope="col">
                                                        <i class="bi bi-wind"></i> Vent
                                                    </th>
                                                    <th scope="col">
                                                        <i class="bi bi-arrow-clockwise"></i> Provenance Vent
                                                    </th>
                                                    <th scope="col">
                                                        <i class="bi bi-activity"></i> Impact
                                                    </th>
                                                    <th scope="col">
                                                        <i class="bi bi-clock"></i> Temps
                                                    </th>
                                                </tr>
                                            </thead>
                                            <tbody></tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Message de bienvenue -->
                <div id="welcome-message" class="text-center py-5">
                    <i class="bi bi-bicycle display-1 text-muted"></i>
                    <h2 class="text-muted mt-3">Bienvenue sur RideFlow</h2>
                    <p class="text-muted fs-5">
                        Chargez un fichier GPX pour commencer l'analyse de votre parcours cycliste 
                        optimisé selon les conditions de vent.
                    </p>
                    
                    <div class="mt-4">
                        <div class="row justify-content-center">
                            <div class="col-md-8">
                                <div class="alert alert-light border">
                                    <h6 class="mb-3">
                                        <i class="bi bi-info-circle text-primary"></i> 
                                        Comment utiliser RideFlow :
                                    </h6>
                                    <ol class="text-start mb-0">
                                        <li class="mb-2">
                                            📁 <strong>Chargez votre fichier GPX</strong> 
                                            (track, route ou waypoints)
                                        </li>
                                        <li class="mb-2">
                                            📅 <strong>Sélectionnez la date et l'heure</strong> 
                                            de votre sortie prévue
                                        </li>
                                        <li class="mb-2">
                                            🚴 <strong>Indiquez votre vitesse moyenne</strong> 
                                            habituelle
                                        </li>
                                        <li class="mb-2">
                                            🌬️ <strong>Cliquez sur "Analyser"</strong> 
                                            pour obtenir les conditions de vent
                                        </li>
                                        <li class="mb-0">
                                            📊 <strong>Consultez les recommandations</strong> 
                                            pour optimiser votre parcours
                                        </li>
                                    </ol>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mt-3">
                            <small class="text-muted">
                                <i class="bi bi-file-earmark-code"></i> 
                                Formats supportés: .gpx avec points de track (&lt;trkpt&gt;), 
                                route (&lt;rtept&gt;) ou waypoints (&lt;wpt&gt;)
                            </small>
                        </div>
                    </div>
                </div>
                
                <!-- Zone d'erreur -->
                <div id="error" class="mt-3" role="alert" aria-live="polite"></div>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="bg-light border-top mt-5 py-4">
        <div class="container-fluid">
            <div class="row align-items-center">
                <div class="col-md-6">
                    <small class="text-muted">
                        <i class="bi bi-info-circle"></i> 
                        RideFlow utilise l'API gratuite 
                        <a href="https://open-meteo.com" target="_blank" rel="noopener">Open-Meteo</a> 
                        pour les prévisions météorologiques.
                    </small>
                </div>
                <div class="col-md-6 text-md-end mt-2 mt-md-0">
                    <small class="text-muted">
                        <i class="bi bi-code-slash"></i> 
                        RideFlow v2.1 - Analyseur de conditions de vent pour cyclistes
                    </small>
                </div>
            </div>
        </div>
    </footer>
    
    <!-- Scripts JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="assets/app.js"></script>
</body>
</html>