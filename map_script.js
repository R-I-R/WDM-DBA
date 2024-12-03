// Initialize QWebChannel
document.addEventListener("DOMContentLoaded", function(event) {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        window.channel = channel;
        window.backend = channel.objects.backend;
        initializeMap();

        backend.addMarkerSignal.connect(addMarker);
        backend.addConnectionSignal.connect(addConnection);
		// backend.changeLineColorSignal.connect(changeLineColor);
		backend.highlightConnectionsSignal.connect(highlightConnections);
        backend.selectedComponentTypeChanged.connect(function(){
            backend.log(backend.selectedComponentType);
        });
		backend.cleanMapSignal.connect(function(){
			map.eachLayer(function(layer){
				if(layer.id != undefined)
					map.removeLayer(layer);
			});
		});

    });
});

function initializeMap() {
    window.map = Object.values(window).find(obj => obj instanceof L.Map);
	window.selectedMarkers = [];
    if (map) {
        map.on('click', function(e) {
            var coords = e.latlng;
            backend.handleMapClick(coords.lat, coords.lng);
        });
    }
}

function addMarker(lat, lng, componentType, id, iconUrl) {
    if (map) {
        let icon = L.icon({
            iconUrl: iconUrl,
            iconSize: [40, 40], // size of the icon
            iconAnchor: [20, 20], // point of the icon which will correspond to marker's location
            popupAnchor: [1, -34], // point from which the popup should open relative to the iconAnchor
        });

        let mk = L.marker([lat, lng], { icon: icon })
            .addTo(map)
            .on('dblclick', function(e){ backend.removeComponent(e.target.id); map.removeLayer(e.target); })
			.on('click', function(e){ backend.handleMarkerClick(e.target.id); })
            .bindPopup(componentType);
        mk.id = id;

        if (componentType === "ONUNode") {
            backend.getBandwidth(id, function(bandwidth) {
                mk.bindPopup(`${componentType}<br>Bandwidth: ${bandwidth} Mbps`);
            });
        }
    }
}

function addConnection(lat1, lng1, lat2, lng2, id, color) {
    if (map) {
        let line = L.polyline([
            [lat1, lng1],
            [lat2, lng2]
        ], {color: color})
        .addTo(map)
        .on('dblclick', function(e){ backend.removeComponent(e.target.id); map.removeLayer(e.target); });
        line.id = id;
		line.type_ = "connection";
    }
}

function changeLineColor(id, newColor) {
	map.eachLayer(function(layer){
		if(layer.id === id){
			layer.setStyle({ color: newColor });
		}
	});
}

function highlightConnections(ids, higlight_color, normal_color){
	ids = ids.split(',');

	map.eachLayer(function(layer){
		if(layer.type_ == "connection"){
			
			map.removeLayer(layer);
			let line = L.polyline(layer.getLatLngs(), {color: ids.includes(layer.id) ? higlight_color: normal_color})
			.addTo(map)
			.on('dblclick', function(e){ backend.removeComponent(e.target.id); map.removeLayer(e.target); });
			line.id = layer.id;
			line.type_ = "connection";
		}
		
	});
}
