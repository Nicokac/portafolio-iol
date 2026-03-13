from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache


class RateLimitedLoginView(LoginView):
    lockout_message = "Too many login attempts. Please wait a few minutes and try again."

    def get_rate_limit_key(self) -> str:
        username = (self.request.POST.get("username") or "").strip().lower()
        ip_address = self.request.META.get("REMOTE_ADDR", "unknown")
        return f"login_attempts:{ip_address}:{username}"

    def get_lockout_threshold(self) -> int:
        return int(getattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 5))

    def get_lockout_window(self) -> int:
        return int(getattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 900))

    def is_locked_out(self, key: str) -> bool:
        return int(cache.get(key, 0)) >= self.get_lockout_threshold()

    def register_failure(self, key: str) -> None:
        if cache.add(key, 1, timeout=self.get_lockout_window()):
            return
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=self.get_lockout_window())

    def clear_failures(self, key: str) -> None:
        cache.delete(key)

    def post(self, request, *args, **kwargs):
        key = self.get_rate_limit_key()
        if self.is_locked_out(key):
            form = self.get_form()
            form.add_error(None, self.lockout_message)
            return self.render_to_response(self.get_context_data(form=form), status=429)

        response = super().post(request, *args, **kwargs)
        if response.status_code == 302:
            self.clear_failures(key)
        else:
            self.register_failure(key)
        return response


__all__ = ["RateLimitedLoginView", "LogoutView"]
