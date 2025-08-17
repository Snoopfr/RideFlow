/**
 * RideFlow Application - Version Refactorisée v2.1
 * Analyseur de conditions de vent pour cyclistes
 */

class RideFlow {
    constructor() {
        this.gpxData = null;
        this.windData = null;
        this.map = null;
        this.charts = {
            windRose: null,
            windImpact: null
        };
        
        this.init();
    }

    /**
     * Initialisation de l'application
     */
    async init() {
        this.setupEventListeners();
        await this.initializeMap();
        this.initializeDateTime();
    }

    /**
     * Configuration des écouteurs d'événements
     */
    setupEventListeners() {
        const elements = {
            fileInput: document.getElementById('gpx-file'),
            analyzeBtn: document.getElementById('analyze-btn'),
            clearBtn: document.getElementById('clear-btn')
        };

        if (elements.fileInput) {
            elements.fileInput.addEventListener('change', (e) => {
                this.handleFileUpload(e.target.files[0]);
                if (elements.analyzeBtn) {
                    elements.analyzeBtn.disabled = !e.target.files.length;
                }
            });
        }

        if (elements.analyzeBtn) {
            elements.analyzeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (!elements.analyzeBtn.disabled) {
                    this.confirmAndAnalyzeWind();
                }
            });
        }

        if (elements.clearBtn) {
            elements.clearBtn.addEventListener('click', () => this.clearAll());
        }
    }

    /**
     * Initialisation de la carte avec gestion d'erreurs robuste
     */
    async initializeMap() {
        const mapDiv = document.getElementById('map');
        if (!mapDiv || this.map) return;

        try {
            // Forcer les dimensions CSS immédiatement
            this.setMapDimensions(mapDiv);
            
            // Attendre que l'élément soit visible dans le DOM
            await this.waitForMapVisibility(mapDiv);
            
            // Créer la carte Leaflet
            this.createLeafletMap();
            
        } catch (error) {
            console.error('Erreur initialisation carte:', error);
            this.showError('Erreur lors de l\'initialisation de la carte');
        }
    }

    /**
     * Configuration des dimensions de la carte
     */
    setMapDimensions(mapDiv) {
        const styles = {
            height: '500px',
            width: '100%',
            display: 'block',
            visibility: 'visible',
            position: 'relative',
            backgroundColor: '#f8f9fa'
        };
        
        Object.assign(mapDiv.style, styles);
    }

    /**
     * Attendre que la carte soit visible avec IntersectionObserver
     */
    waitForMapVisibility(mapDiv) {
        return new Promise((resolve) => {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting || entry.intersectionRatio > 0) {
                        observer.disconnect();
                        resolve();
                    }
                });
            }, { threshold: 0.1 });
            
            observer.observe(mapDiv);
            
            // Fallback après 3 secondes
            setTimeout(() => {
                observer.disconnect();
                resolve();
            }, 3000);
        });
    }

    /**
     * Création de la carte Leaflet
     */
    createLeafletMap() {
        const mapOptions = {
            center: [48.8566, 2.3522],
            zoom: 10,
            zoomControl: true,
            scrollWheelZoom: true,
            preferCanvas: false
        };

        this.map = L.map('map', mapOptions);

        // Couche de tuiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 18,
            detectRetina: true,
            updateWhenIdle: false,
            keepBuffer: 2
        }).addTo(this.map);

        // Gestion des événements de carte
        this.map.whenReady(() => {
            setTimeout(() => {
                this.map.invalidateSize(true);
                if (this.gpxData) {
                    this.displayRouteOnMap();
                }
            }, 100);
        });

        // Marquer comme prête
        document.getElementById('map').classList.add('map-ready');
    }

    /**
     * Gestion du téléchargement de fichier GPX
     */
    async handleFileUpload(file) {
        if (!file) {
            this.showError('Veuillez sélectionner un fichier GPX');
            return;
        }

        if (!file.name.toLowerCase().endsWith('.gpx')) {
            this.showError('Veuillez sélectionner un fichier avec l\'extension .gpx');
            return;
        }

        const formData = new FormData();
        formData.append('action', 'parse_gpx');
        formData.append('gpx', file);

        try {
            this.toggleLoading(true);
            const response = await this.apiRequest('functions.php', {
                method: 'POST',
                body: formData
            });

            if (response.success) {
                this.gpxData = response.data;
                this.displayGpxInfo();
                this.displayRouteOnMap();
                this.enableAnalysis();
            } else {
                throw new Error(response.error || 'Erreur lors du traitement du GPX');
            }

        } catch (error) {
            console.error('Erreur upload GPX:', error);
            this.showError('Erreur lors du chargement: ' + error.message);
        } finally {
            this.toggleLoading(false);
        }
    }

    /**
     * Confirmation et analyse du vent
     */
    confirmAndAnalyzeWind() {
        const confirmed = confirm(
            'L\'analyse météorologique va effectuer un appel API.\n' +
            'Les données de vent seront récupérées pour optimiser votre parcours.\n\n' +
            'Continuer ?'
        );
        
        if (confirmed) {
            this.analyzeWind();
        }
    }

    /**
     * Analyse des conditions de vent
     */
    async analyzeWind() {
        if (!this.gpxData) {
            this.showError('Aucune donnée GPX disponible');
            return;
        }

        const formData = this.getAnalysisFormData();
        if (!formData) return;

        try {
            this.toggleLoading(true);
            const response = await this.apiRequest('functions.php', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (response.success) {
                this.windData = response.data;
                this.displayResults();
            } else {
                throw new Error(response.error || 'Erreur lors de l\'analyse');
            }

        } catch (error) {
            console.error('Erreur analyse vent:', error);
            this.showError('Erreur lors de l\'analyse météorologique: ' + error.message);
        } finally {
            this.toggleLoading(false);
        }
    }

    /**
     * Récupération des données du formulaire d'analyse
     */
    getAnalysisFormData() {
        const datetimeInput = document.getElementById('ride-datetime');
        const riderSpeedInput = document.getElementById('rider-speed');
        
        const datetime = datetimeInput?.value;
        const riderSpeed = riderSpeedInput ? parseFloat(riderSpeedInput.value) : NaN;

        if (!datetime || isNaN(riderSpeed)) {
            this.showError('Veuillez spécifier une date/heure et une vitesse valide');
            return null;
        }

        return {
            action: 'analyze_wind',
            segments: this.gpxData.segments,
            datetime: datetime,
            rider_speed: riderSpeed
        };
    }

    /**
     * Requête API générique avec gestion d'erreurs
     */
    async apiRequest(url, options) {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const text = await response.text();
        
        try {
            return JSON.parse(text);
        } catch (e) {
            console.error('Erreur parsing JSON:', e, 'Réponse:', text.substring(0, 200));
            throw new Error('Réponse serveur invalide');
        }
    }

    /**
     * Affichage des informations GPX
     */
    displayGpxInfo() {
        if (!this.gpxData) return;

        const elements = {
            info: document.getElementById('gpx-info'),
            name: document.getElementById('gpx-name'),
            distance: document.getElementById('gpx-distance'),
            points: document.getElementById('gpx-points')
        };

        if (elements.name) elements.name.textContent = this.gpxData.name;
        if (elements.distance) elements.distance.textContent = this.gpxData.total_distance;
        if (elements.points) elements.points.textContent = this.gpxData.total_points;
        
        if (elements.info) {
            elements.info.style.display = 'block';
            
            // Ajouter les informations de parcours
            if (this.gpxData.route_info) {
                this.addRouteInfo(elements.info);
            }
        }
    }

    /**
     * Ajout des informations de parcours
     */
    addRouteInfo(container) {
        const existingInfo = container.querySelector('.route-info');
        if (existingInfo) existingInfo.remove();

        const routeInfo = document.createElement('div');
        routeInfo.className = 'alert alert-success mt-2 route-info';
        routeInfo.innerHTML = `
            <small>
                <strong>Type de parcours:</strong><br>
                ${this.gpxData.route_info.description}
            </small>
        `;
        container.appendChild(routeInfo);
    }

    /**
     * Affichage de la route sur la carte
     */
    displayRouteOnMap() {
        if (!this.gpxData || !this.map) return;

        // Nettoyer les couches existantes
        this.clearMapLayers();

        const coords = this.validateCoordinates();
        if (!coords.length) return;

        // Afficher le tracé (coloré si analyse vent disponible)
        if (this.windData?.segments) {
            this.createColoredRoute(coords);
            this.showLegend();
        } else {
            this.createSimpleRoute(coords);
            this.hideLegend();
        }

        // Ajouter les marqueurs de début/fin
        this.addStartEndMarkers(coords);

        // Ajuster la vue de la carte
        this.fitMapToRoute(coords);

        // Ajouter la flèche de vent si disponible
        if (this.windData?.dominant_wind) {
            setTimeout(() => this.addWindIndicator(), 300);
        }

        this.hideWelcomeMessage();
    }

    /**
     * Validation et préparation des coordonnées
     */
    validateCoordinates() {
        return this.gpxData.points
            .map(pt => {
                if (!pt.lat || !pt.lon || isNaN(pt.lat) || isNaN(pt.lon)) {
                    return null;
                }
                return [parseFloat(pt.lat), parseFloat(pt.lon)];
            })
            .filter(coord => coord !== null);
    }

    /**
     * Nettoyage des couches de la carte
     */
    clearMapLayers() {
        this.map.eachLayer(layer => {
            if (layer instanceof L.Polyline || 
                layer instanceof L.Marker || 
                layer instanceof L.CircleMarker) {
                this.map.removeLayer(layer);
            }
        });
    }

    /**
     * Création d'une route simple (sans analyse vent)
     */
    createSimpleRoute(coords) {
        L.polyline(coords, { 
            color: '#0066cc', 
            weight: 4,
            opacity: 0.8,
            smoothFactor: 1.0
        }).addTo(this.map);
    }

    /**
     * Création d'une route colorée selon l'analyse vent
     */
    createColoredRoute(coords) {
        const segments = this.windData.segments;
        
        for (let i = 0; i < Math.min(segments.length, coords.length - 1); i++) {
            const segment = segments[i];
            const segmentCoords = [coords[i], coords[i + 1]];
            
            if (!segmentCoords[0] || !segmentCoords[1]) continue;
            
            const style = this.getSegmentStyle(segment.wind_impact);
            
            const segmentLine = L.polyline(segmentCoords, style).addTo(this.map);
            
            // Popup avec informations détaillées
            segmentLine.bindPopup(this.createSegmentPopup(segment, i + 1));
            
            // Effets hover
            this.addSegmentInteractivity(segmentLine, style);
        }
    }

    /**
     * Style d'un segment selon l'impact du vent
     */
    getSegmentStyle(windImpact) {
        const styles = {
            favorable: { color: '#28a745', weight: 7, opacity: 0.9 },
            unfavorable: { color: '#dc3545', weight: 7, opacity: 0.9 },
            crosswind: { color: '#ffc107', weight: 6, opacity: 0.8 },
            default: { color: '#6c757d', weight: 5, opacity: 0.7 }
        };
        
        return {
            ...styles[windImpact] || styles.default,
            smoothFactor: 1.0,
            className: `segment-${windImpact || 'mixed'}`,
            interactive: true
        };
    }

    /**
     * Création du popup d'information pour un segment
     */
    createSegmentPopup(segment, segmentNumber) {
        const impactText = this.getImpactText(segment.wind_impact);
        const color = this.getSegmentStyle(segment.wind_impact).color;
        
        return `
            <div style="min-width: 200px;">
                <b>Segment ${segmentNumber}</b><br>
                <strong>Distance:</strong> ${segment.distance.toFixed(2)} km<br>
                <strong>Direction:</strong> ${segment.bearing_text} (${segment.bearing.toFixed(0)}°)<br>
                <strong>Vent:</strong> ${segment.wind_speed} km/h (provient du ${segment.wind_direction_text})<br>
                <strong>Impact:</strong> <span style="color: ${color}; font-weight: bold">${impactText}</span><br>
                <strong>Temps estimé:</strong> ${segment.estimated_time_minutes.toFixed(1)} min
            </div>
        `;
    }

    /**
     * Ajout de l'interactivité aux segments
     */
    addSegmentInteractivity(segmentLine, originalStyle) {
        segmentLine.on('mouseover', function() {
            this.setStyle({
                weight: originalStyle.weight + 2,
                opacity: Math.min(originalStyle.opacity + 0.2, 1.0)
            });
        });
        
        segmentLine.on('mouseout', function() {
            this.setStyle(originalStyle);
        });
    }

    /**
     * Texte descriptif de l'impact du vent
     */
    getImpactText(impact) {
        const impacts = {
            favorable: 'Favorable (vent arrière)',
            unfavorable: 'Défavorable (vent de face)',
            crosswind: 'Vent de travers',
            default: 'Mixte/Indéterminé'
        };
        return impacts[impact] || impacts.default;
    }

    /**
     * Ajout des marqueurs de début et fin
     */
    addStartEndMarkers(coords) {
        if (!coords.length) return;

        // Marqueur de départ
        L.circleMarker(coords[0], {
            color: 'green',
            fillColor: 'lightgreen',
            fillOpacity: 0.8,
            radius: 10
        }).addTo(this.map).bindPopup('<b>Départ</b>');

        // Marqueur d'arrivée (seulement si différent du départ)
        const isLoop = this.calculateDistance(coords[0], coords[coords.length - 1]) < 0.001;
        if (!isLoop) {
            L.circleMarker(coords[coords.length - 1], {
                color: 'red',
                fillColor: 'lightcoral',
                fillOpacity: 0.8,
                radius: 10
            }).addTo(this.map).bindPopup('<b>Arrivée</b>');
        }
    }

    /**
     * Ajustement de la vue de la carte au parcours
     */
    fitMapToRoute(coords) {
        setTimeout(() => {
            if (this.map && coords.length > 0) {
                this.map.invalidateSize(true);
                
                try {
                    this.map.fitBounds(L.latLngBounds(coords), { 
                        padding: [20, 20],
                        maxZoom: 15
                    });
                } catch (error) {
                    console.error('Erreur centrage carte:', error);
                    this.map.setView(coords[0], 13);
                }
                
                setTimeout(() => this.map.invalidateSize(true), 100);
            }
        }, 200);
    }

    /**
     * Ajout de l'indicateur de vent central
     */
    addWindIndicator() {
        if (!this.windData?.center_point || !this.windData?.dominant_wind) return;

        const { center_point, dominant_wind } = this.windData;
        
        // Direction où VA le vent (inverse de d'où il vient)
        const arrowDirection = (dominant_wind.direction + 180) % 360;
        
        const windIcon = L.divIcon({
            className: 'wind-indicator-new',
            html: this.createWindArrowHTML(arrowDirection, dominant_wind.speed),
            iconSize: [50, 70],
            iconAnchor: [25, 25]
        });

        L.marker([center_point.lat, center_point.lon], { icon: windIcon })
            .addTo(this.map)
            .bindPopup(this.createWindPopup(dominant_wind));
    }

    /**
     * Création du HTML de la flèche de vent
     */
    createWindArrowHTML(direction, speed) {
        return `
            <div class="wind-arrow-container" style="transform: rotate(${direction}deg)">
                <svg class="wind-arrow-svg" width="50" height="50" viewBox="0 0 50 50">
                    <circle cx="25" cy="25" r="22" fill="rgba(255,255,255,0.95)" 
                            stroke="#0066cc" stroke-width="3"/>
                    <path d="M25 8 L32 20 L28 20 L28 35 L22 35 L22 20 L18 20 Z" 
                          fill="#0066cc" stroke="#fff" stroke-width="1"/>
                    <circle cx="25" cy="10" r="2" fill="#ff6b35"/>
                </svg>
                <div class="wind-speed-display">${speed} km/h</div>
            </div>
        `;
    }

    /**
     * Création du popup d'information vent
     */
    createWindPopup(dominantWind) {
        const windFromText = this.bearingToText(dominantWind.direction);
        const windToText = this.bearingToText((dominantWind.direction + 180) % 360);
        
        return `
            <div style="text-align: center; min-width: 150px;">
                <b>🌬️ Vent Dominant</b><br>
                <strong>Vient du:</strong> ${windFromText}<br>
                <strong>Va vers:</strong> ${windToText}<br>
                <strong>Vitesse:</strong> ${dominantWind.speed} km/h<br>
                <small style="color: #666;">La flèche indique où va le vent</small>
            </div>
        `;
    }

    /**
     * Affichage des résultats complets
     */
    displayResults() {
        if (!this.windData) return;

        // Redessiner la carte avec tracé coloré
        this.displayRouteOnMap();
        
        // Afficher les sections de résultats
        this.showResultsSections();
        
        // Afficher recommandations
        this.displayRecommendations();
        
        // Remplir le tableau des segments
        this.populateSegmentsTable();
        
        // Mettre à jour les graphiques
        this.updateCharts();
    }

    /**
     * Affichage des sections de résultats
     */
    showResultsSections() {
        const elements = {
            results: document.getElementById('results-section'),
            legend: document.getElementById('legend-card')
        };

        if (elements.results) elements.results.style.display = 'block';
        if (elements.legend) elements.legend.style.display = 'block';
    }

    /**
     * Affichage des recommandations
     */
    displayRecommendations() {
        const recommendationsDiv = document.getElementById('recommendations-content');
        if (!recommendationsDiv || !this.windData.summary) return;

        const { summary, dominant_wind } = this.windData;
        
        recommendationsDiv.innerHTML = this.generateRecommendationsHTML(summary, dominant_wind);
    }

    /**
     * Génération du HTML des recommandations
     */
    generateRecommendationsHTML(summary, dominantWind) {
        const bestDirectionText = summary.best_direction === 'normal' ? 
            'Sens normal (départ → arrivée)' : 'Sens inverse (arrivée → départ)';
        
        const windFromText = this.bearingToText(dominantWind.direction);
        const windToText = this.bearingToText((dominantWind.direction + 180) % 360);
        const windArrow = this.getWindDirectionArrow(windFromText);

        return `
            <div class="row">
                <div class="col-md-6">
                    <div class="recommendation-box">
                        <h6><i class="bi bi-compass"></i> Recommandation</h6>
                        <div class="alert ${summary.best_direction === 'normal' ? 'alert-success' : 'alert-info'}">
                            <strong>${bestDirectionText}</strong><br>
                            <small>${this.getTimeSavingsText(summary.time_saved_minutes)}</small>
                        </div>
                    </div>
                    ${this.generateTimingInfo(summary)}
                </div>
                <div class="col-md-6">
                    ${this.generateWindInfo(dominantWind, windArrow, windFromText, windToText, summary)}
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-12">
                    <div class="alert alert-info">
                        <strong>💡 Conseil:</strong> 
                        ${this.generateAdvice(summary)}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Génération du texte d'économie de temps
     */
    getTimeSavingsText(timeSavedMinutes) {
        return timeSavedMinutes > 0.5 ? 
            `Économise ${this.formatTime(timeSavedMinutes)}` : 
            'Pas de différence significative';
    }

    /**
     * Génération des informations de timing
     */
    generateTimingInfo(summary) {
        return `
            <p><strong>Temps estimé (sens normal):</strong> ${this.formatTime(summary.total_time_normal)}</p>
            <p><strong>Temps estimé (sens inverse):</strong> ${this.formatTime(summary.total_time_reverse)}</p>
            <p><strong>Différence:</strong> 
                <span class="text-${this.getTimeDifferenceClass(summary.time_saved_minutes)}">
                    ${summary.time_saved_minutes > 0.5 ? this.formatTime(summary.time_saved_minutes) : 'Négligeable'}
                </span>
            </p>
        `;
    }

    /**
     * Génération des informations de vent
     */
    generateWindInfo(dominantWind, windArrow, windFromText, windToText, summary) {
        return `
            <p><strong>Vent dominant:</strong> ${windArrow} Provenance: ${windFromText} → Direction: ${windToText} (${dominantWind.speed} km/h)</p>
            <p><strong>Distance totale:</strong> ${summary.total_distance} km</p>
            <p><strong>Vent de face (normal):</strong> <span class="text-danger">${summary.headwind_distance_normal.toFixed(1)} km</span></p>
            <p><strong>Vent de face (inverse):</strong> <span class="text-danger">${summary.headwind_distance_reverse.toFixed(1)} km</span></p>
        `;
    }

    /**
     * Remplissage du tableau des segments
     */
    populateSegmentsTable() {
        const tableBody = document.querySelector('#segments-table tbody');
        if (!tableBody || !this.windData.segments) return;

        tableBody.innerHTML = '';
        
        const segmentGroups = this.groupSegments(this.windData.segments, 20);
        
        segmentGroups.forEach(group => {
            const row = this.createSegmentTableRow(group);
            tableBody.appendChild(row);
        });
    }

    /**
     * Groupement des segments pour le tableau
     */
    groupSegments(segments, maxPerGroup) {
        const groups = [];
        for (let i = 0; i < segments.length; i += maxPerGroup) {
            groups.push(segments.slice(i, i + maxPerGroup));
        }
        return groups;
    }

    /**
     * Création d'une ligne du tableau de segments
     */
    createSegmentTableRow(group) {
        const stats = this.calculateGroupStats(group);
        console.log('stats.avgWindDirection:', stats.avgWindDirection); // <-- à supprimer
        const row = document.createElement('tr');
        
        row.innerHTML = `
            <td>Segments ${stats.range}</td>
            <td>${stats.totalDistance.toFixed(2)} km</td>
            <td>${this.getDirectionIcon(group[0].bearing_text)}</td>
            <td>${stats.avgWind.toFixed(1)} km/h</td>
            <td>${this.getWindDirectionArrow(this.windData.dominant_wind.direction_text)}</td>
            <td>${this.createImpactBadge(stats.dominantImpact)}</td>
            <td>${stats.totalTime.toFixed(0)} min</td>
        `;
        
        return row;
    }

    /**
     * Calcul des statistiques d'un groupe de segments
     */
    calculateGroupStats(group) {
        const startSegment = group[0].id + 1;
        const endSegment = group[group.length - 1].id + 1;
        
        // Calculer la direction moyenne du vent (pas du parcours)
        const avgWindDirection = group.reduce((sum, s) => sum + s.wind_direction, 0) / group.length;
        const avgWindDirectionText = this.bearingToText(avgWindDirection);
        
        return {
            range: startSegment === endSegment ? `${startSegment}` : `${startSegment}-${endSegment}`,
            avgWind: group.reduce((sum, s) => sum + s.wind_speed, 0) / group.length,
            avgWindDirection: avgWindDirectionText,
            totalDistance: group.reduce((sum, s) => sum + s.distance, 0),
            totalTime: group.reduce((sum, s) => sum + s.estimated_time_minutes, 0),
            dominantImpact: this.getDominantImpact(group)
        };
    }

    /**
     * Détermination de l'impact dominant d'un groupe
     */
    getDominantImpact(segmentGroup) {
        const impacts = segmentGroup.map(s => s.wind_impact);
        const counts = {
            favorable: impacts.filter(i => i === 'favorable').length,
            unfavorable: impacts.filter(i => i === 'unfavorable').length,
            crosswind: impacts.filter(i => i === 'crosswind').length
        };
        
        if (counts.favorable > counts.unfavorable && counts.favorable > counts.crosswind) {
            return 'favorable';
        }
        if (counts.unfavorable > counts.favorable && counts.unfavorable > counts.crosswind) {
            return 'unfavorable';
        }
        return 'mixed';
    }

    /**
     * Création d'un badge d'impact
     */
    createImpactBadge(impact) {
        const badges = {
            favorable: '<span class="badge bg-success">Favorable</span>',
            unfavorable: '<span class="badge bg-danger">Défavorable</span>',
            mixed: '<span class="badge bg-warning">Mixte</span>'
        };
        return badges[impact] || badges.mixed;
    }

    /**
     * Mise à jour des graphiques
     */
    updateCharts() {
        this.updateWindRoseChart();
        this.updateWindImpactChart();
    }

    /**
     * Graphique rose des vents
     */
    updateWindRoseChart() {
        const ctx = document.getElementById('wind-rose-chart');
        if (!ctx) return;

        if (this.charts.windRose) {
            this.charts.windRose.destroy();
        }

        this.charts.windRose = new Chart(ctx, {
            type: 'polarArea',
            data: {
                labels: ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
                datasets: [{
                    label: 'Intensité du vent (km/h)',
                    data: this.calculateWindRoseData(),
                    backgroundColor: [
                        'rgba(75, 192, 192, 0.6)', 'rgba(54, 162, 235, 0.6)',
                        'rgba(255, 206, 86, 0.6)', 'rgba(255, 99, 132, 0.6)',
                        'rgba(153, 102, 255, 0.6)', 'rgba(255, 159, 64, 0.6)',
                        'rgba(199, 199, 199, 0.6)', 'rgba(83, 102, 255, 0.6)'
                    ],
                    borderWidth: 2,
                    borderColor: 'rgba(255, 255, 255, 0.8)'
                }]
            },
            options: {
                responsive: true,
                plugins: { 
                    legend: { position: 'bottom' },
                    title: { display: true, text: 'Rose des vents' }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        title: { display: true, text: 'km/h' }
                    }
                }
            }
        });
    }

    /**
     * Graphique de comparaison des temps
     */
    updateWindImpactChart() {
        const ctx = document.getElementById('wind-impact-chart');
        if (!ctx) return;

        if (this.charts.windImpact) {
            this.charts.windImpact.destroy();
        }

        const summary = this.windData.summary;
        
        this.charts.windImpact = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Sens Normal', 'Sens Inverse'],
                datasets: [{
                    label: 'Temps de parcours (minutes)',
                    data: [summary.total_time_normal, summary.total_time_reverse],
                    backgroundColor: [
                        summary.best_direction === 'normal' ? 'rgba(40, 167, 69, 0.8)' : 'rgba(220, 53, 69, 0.8)',
                        summary.best_direction === 'reverse' ? 'rgba(40, 167, 69, 0.8)' : 'rgba(220, 53, 69, 0.8)'
                    ],
                    borderColor: [
                        summary.best_direction === 'normal' ? 'rgba(40, 167, 69, 1)' : 'rgba(220, 53, 69, 1)',
                        summary.best_direction === 'reverse' ? 'rgba(40, 167, 69, 1)' : 'rgba(220, 53, 69, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { 
                        beginAtZero: true, 
                        title: { display: true, text: 'Temps (min)' }
                    }
                },
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: 'Comparaison des temps de parcours' }
                }
            }
        });
    }

    /**
     * Calcul des données pour la rose des vents
     */
    calculateWindRoseData() {
        if (!this.windData?.dominant_wind) return new Array(8).fill(0);
        
        const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
        const counts = new Array(8).fill(0);
        
        const dominantWind = this.windData.dominant_wind;
        let mappedDir = this.mapToCardinalDirection(dominantWind.direction_text);
        
        const index = directions.indexOf(mappedDir);
        if (index !== -1) {
            counts[index] = dominantWind.speed;
        }
        
        return counts;
    }

    /**
     * Mappage vers les directions cardinales principales
     */
    mapToCardinalDirection(direction) {
        const mappings = {
            'NNE': 'NE', 'ENE': 'NE',
            'ESE': 'SE', 'SSE': 'SE',
            'SSO': 'SW', 'OSO': 'SW',
            'ONO': 'NW', 'NNO': 'NW',
            'O': 'W'
        };
        return mappings[direction] || direction;
    }

    /**
     * Fonctions utilitaires
     */

    formatTime(minutes) {
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        return hours > 0 ? `${hours}h${mins.toString().padStart(2, '0')}` : `${mins} min`;
    }

    getTimeDifferenceClass(minutes) {
        if (minutes > 5) return 'success';
        if (minutes > 0.5) return 'warning';
        return 'muted';
    }

    generateAdvice(summary) {
        const timeDiff = summary.time_saved_minutes;
        const direction = summary.best_direction === 'normal' ? 'sens normal' : 'sens inverse';
        
        if (timeDiff < 2) {
            return "L'impact du vent est négligeable. Choisissez selon vos préférences ou contraintes logistiques.";
        } else if (timeDiff < 10) {
            return `Impact modéré du vent : ${this.formatTime(timeDiff)} d'économie en choisissant le ${direction}.`;
        } else {
            const headwindDiff = summary.best_direction === 'normal' ? 
                summary.headwind_distance_reverse - summary.headwind_distance_normal :
                summary.headwind_distance_normal - summary.headwind_distance_reverse;
            return `Impact significatif ! En choisissant le ${direction}, vous économiserez ${this.formatTime(timeDiff)} et éviterez ${headwindDiff.toFixed(1)}km de vent de face supplémentaire.`;
        }
    }

    getWindDirectionArrow(direction) {
        const arrows = {
            'N': '⬇️', 'NNE': '⬇️', 'NE': '↙️', 'ENE': '↙️',
            'E': '⬅️', 'ESE': '↖️', 'SE': '↖️', 'SSE': '↖️',
            'S': '⬆️', 'SSO': '↗️', 'SO': '↗️', 'OSO': '↗️',
            'O': '➡️', 'ONO': '↘️', 'NO': '↘️', 'NNO': '↘️'
        };
        return arrows[direction] || '🌀';
    }

    bearingToText(bearing) {
        const directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                           'S', 'SSO', 'SO', 'OSO', 'O', 'ONO', 'NO', 'NNO'];
        const index = Math.round(bearing / 22.5) % 16;
        return directions[index];
    }
    /**
 * Convertit une direction textuelle en icône de direction
 */
getDirectionIcon(direction) {
    const directionIcons = {
        'N': '⬆️',
        'NNE': '↗️', 
        'NE': '↗️',
        'ENE': '↗️',
        'E': '➡️',
        'ESE': '↘️',
        'SE': '↘️', 
        'SSE': '↘️',
        'S': '⬇️',
        'SSO': '↙️',
        'SO': '↙️',
        'OSO': '↙️', 
        'O': '⬅️',
        'ONO': '↖️',
        'NO': '↖️',
        'NNO': '↖️'
    };
    
    return directionIcons[direction] || '🧭';
}
    calculateDistance(coord1, coord2) {
        const R = 6371;
        const lat1 = coord1[0] * Math.PI / 180;
        const lat2 = coord2[0] * Math.PI / 180;
        const deltaLat = (coord2[0] - coord1[0]) * Math.PI / 180;
        const deltaLon = (coord2[1] - coord1[1]) * Math.PI / 180;

        const a = Math.sin(deltaLat / 2) ** 2 +
                Math.cos(lat1) * Math.cos(lat2) *
                Math.sin(deltaLon / 2) ** 2;
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }

    /**
     * Gestion des éléments UI
     */

    showError(message) {
        const errorDiv = document.getElementById('error');
        if (!errorDiv) return;

        errorDiv.innerHTML = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <i class="bi bi-exclamation-triangle-fill"></i> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        setTimeout(() => {
            const alert = errorDiv.querySelector('.alert');
            if (alert) alert.remove();
        }, 10000);
    }

    toggleLoading(show) {
        const elements = {
            loading: document.getElementById('loading-spinner'),
            analyzeBtn: document.getElementById('analyze-btn'),
            clearBtn: document.getElementById('clear-btn')
        };

        if (elements.loading) {
            elements.loading.style.display = show ? 'block' : 'none';
        }
        if (elements.analyzeBtn) elements.analyzeBtn.disabled = show;
        if (elements.clearBtn) elements.clearBtn.disabled = show;
    }

    enableAnalysis() {
        const analyzeBtn = document.getElementById('analyze-btn');
        if (analyzeBtn) analyzeBtn.disabled = false;
    }

    showLegend() {
        const legend = document.getElementById('legend-card');
        if (legend) legend.style.display = 'block';
    }

    hideLegend() {
        const legend = document.getElementById('legend-card');
        if (legend) legend.style.display = 'none';
    }

    hideWelcomeMessage() {
        const welcome = document.getElementById('welcome-message');
        if (welcome) welcome.style.display = 'none';
    }

    initializeDateTime() {
        const now = new Date();
        const localDateTime = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
            .toISOString().slice(0, 16);
        
        const datetimeInput = document.getElementById('ride-datetime');
        if (datetimeInput) {
            datetimeInput.value = localDateTime;
        }
    }

    /**
     * Remise à zéro complète
     */
    clearAll() {
        // Reset des données
        this.gpxData = null;
        this.windData = null;
        
        // Destruction des graphiques
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = { windRose: null, windImpact: null };
        
        // Reset de l'interface
        const elements = {
            'gpx-info': 'none',
            'results-section': 'none', 
            'legend-card': 'none',
            'welcome-message': 'block'
        };
        
        Object.entries(elements).forEach(([id, display]) => {
            const element = document.getElementById(id);
            if (element) element.style.display = display;
        });
        
        // Nettoyage
        const errorDiv = document.getElementById('error');
        const fileInput = document.getElementById('gpx-file');
        const analyzeBtn = document.getElementById('analyze-btn');
        
        if (errorDiv) errorDiv.innerHTML = '';
        if (fileInput) fileInput.value = '';
        if (analyzeBtn) analyzeBtn.disabled = true;
        
        // Reset de la carte
        if (this.map) {
            this.clearMapLayers();
            this.map.setView([48.8566, 2.3522], 10);
        }
    }
}

/**
 * Initialisation de l'application
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initialisation de RideFlow v2.1');
    
    // Vérifier les dépendances
    if (typeof L === 'undefined') {
        console.error('Leaflet non chargé!');
        return;
    }
    
    if (typeof Chart === 'undefined') {
        console.error('Chart.js non chargé!');
        return;
    }
    
    // Lancer l'application
    new RideFlow();
});