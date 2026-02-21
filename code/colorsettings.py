from flask import Blueprint, jsonify, request
import os
import json
from audit_trail import log_field_change

colorsettings = Blueprint('colorsettings', __name__)


@colorsettings.route('/api/colors', methods=['POST'])
def save_colors():
    new_colors = request.json

    config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
    with open(config_path) as config_file:
        config = json.load(config_file)

    # Capture old values before mutation
    old_text      = config.get('TextColor')
    old_bg        = config.get('BackgroundColor')
    old_sbt       = config.get('SidebarTextColor')
    old_sb        = config.get('SidebarColor')

    config['TextColor']        = new_colors['textColor']
    config['BackgroundColor']  = new_colors['bgColor']
    config['SidebarTextColor'] = new_colors['sbTColor']
    config['SidebarColor']     = new_colors['sbColor']

    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)

    # Audit: log each color field that actually changed
    changes = [
        ('TextColor',        old_text, new_colors['textColor']),
        ('BackgroundColor',  old_bg,   new_colors['bgColor']),
        ('SidebarTextColor', old_sbt,  new_colors['sbTColor']),
        ('SidebarColor',     old_sb,   new_colors['sbColor']),
    ]
    for field_name, old_val, new_val in changes:
        if old_val != new_val:
            log_field_change(
                action_type='UPDATE',
                record_type='SETTING',
                record_id='appconfig',
                field_name=field_name,
                old_value=old_val,
                new_value=new_val,
                change_reason='User updated UI color settings'
            )

    return jsonify(success=True)


@colorsettings.route('/api/colors', methods=['GET'])
def get_colors():
    config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
    with open(config_path) as config_file:
        config = json.load(config_file)

    colors = {
        'textColor': config.get('TextColor'),
        'bgColor':   config.get('BackgroundColor'),
        'sbTColor':  config.get('SidebarTextColor'),
        'sbColor':   config.get('SidebarColor')
    }

    return jsonify(colors)


@colorsettings.route('/api/colors/reset', methods=['POST'])
def reset_colors():
    config_path = os.path.join(os.path.dirname(__file__), 'appconfig.json')
    with open(config_path) as config_file:
        config = json.load(config_file)

    # Capture old values before reset
    old_text = config.get('TextColor')
    old_bg   = config.get('BackgroundColor')
    old_sbt  = config.get('SidebarTextColor')
    old_sb   = config.get('SidebarColor')

    config['TextColor']        = config['defaultTextColor']
    config['BackgroundColor']  = config['defaultBackgroundColor']
    config['SidebarTextColor'] = config['defaultSidebarTextColor']
    config['SidebarColor']     = config['defaultSidebarColor']

    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)

    # Audit: log each color field reset to default
    changes = [
        ('TextColor',        old_text, config['TextColor']),
        ('BackgroundColor',  old_bg,   config['BackgroundColor']),
        ('SidebarTextColor', old_sbt,  config['SidebarTextColor']),
        ('SidebarColor',     old_sb,   config['SidebarColor']),
    ]
    for field_name, old_val, new_val in changes:
        if old_val != new_val:
            log_field_change(
                action_type='UPDATE',
                record_type='SETTING',
                record_id='appconfig',
                field_name=field_name,
                old_value=old_val,
                new_value=new_val,
                change_reason='User reset UI color settings to defaults'
            )

    return jsonify(success=True)
