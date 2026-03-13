from django.urls import path

from apps.users.views import LogoutView, RateLimitedLoginView

app_name = 'users'

urlpatterns = [
    path('login/', RateLimitedLoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
