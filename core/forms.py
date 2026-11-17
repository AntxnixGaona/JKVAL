from django import forms

from .models import PracticeSession


class PracticeSessionForm(forms.ModelForm):
    class Meta:
        model = PracticeSession
        fields = ["player", "exercise", "hits", "attempts"]

    def clean(self):
        cleaned = super().clean()
        hits = cleaned.get("hits")
        attempts = cleaned.get("attempts")
        if attempts is not None and attempts < 1:
            self.add_error("attempts", "Registra al menos un intento.")
        if hits is not None and attempts is not None and hits > attempts:
            self.add_error("hits", "Los aciertos no pueden superar los intentos.")
        return cleaned
