from flask import Blueprint, jsonify, request   
import os
import json

colorsettings = Blueprint('colorsettings', __name__)

# API Call to save the colors
@colorsettings.route('/api/colors', methods=['POST'])
def save_colors():
    new_colors = request.json
    
    # Update the colors in the config file
    config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
    with open(config_path) as config_file:
        config = json.load(config_file)
    
    # Overwrite current color values with new values
    config['TextColor'] = new_colors['textColor']
    config['BackgroundColor'] = new_colors['bgColor']
    config['SidebarTextColor'] = new_colors['sbTColor']
    config['SidebarColor'] = new_colors['sbColor']

    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)
    
    return jsonify(success=True)

@colorsettings.route('/api/colors', methods=['GET'])
def get_colors():
    config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
    with open(config_path) as config_file:
        config = json.load(config_file)
        
    colors = {
            'textColor': config.get('TextColor'),
            'bgColor': config.get('BackgroundColor'),
            'sbTColor': config.get('SidebarTextColor'),
            'sbColor': config.get('SidebarColor')
    }
        
    return jsonify(colors)

@colorsettings.route('/api/colors/reset', methods=['POST'])
def reset_colors():
    config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
    with open(config_path) as config_file:
        config = json.load(config_file)
    
    # Overwrite current color values with default values
    config['TextColor'] = config['defaultTextColor']
    config['BackgroundColor'] = config['defaultBackgroundColor']
    config['SidebarTextColor'] = config['defaultSidebarTextColor']
    config['SidebarColor'] = config['defaultSidebarColor']

    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)

    return jsonify(success=True)

