def ui_preferences(request):
    return {
        'ui_mode': request.session.get('ui_mode', 'compacto'),
        'risk_profile': request.session.get('risk_profile', 'moderado'),
    }
