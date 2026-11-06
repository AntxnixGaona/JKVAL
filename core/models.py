"""Persistencia de rastreadores y partidas de VALORANT.

Modelo mínimo alineado con la respuesta v4 de HenrikDev:
- ``TrackerPlayer``: cuenta pública rastreada (sin credenciales ni datos privados).
- ``TrackerMatch``: metadata de la partida.
- ``TrackerPlayerMatch``: fila por jugador y partida.

Los campos numéricos admiten ``NULL`` para distinguir "dato ausente" de cero.
"""
from django.db import models


class TrackerPlayer(models.Model):
    """Cuenta pública de VALORANT que se desea rastrear."""

    puuid = models.CharField(max_length=78, unique=True)
    name = models.CharField(max_length=64)
    tag = models.CharField(max_length=16)
    region = models.CharField(max_length=16, blank=True)
    platform = models.CharField(max_length=10, default="pc")
    account_level = models.PositiveIntegerField(null=True, blank=True)
    card = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=32, default="henrikdev")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["name", "tag"], name="idx_tracker_player_name_tag"),
        ]

    def __str__(self):
        return f"{self.name}#{self.tag}"


class TrackerMatch(models.Model):
    """Metadata de una partida, tal como la entrega HenrikDev v4."""

    match_id = models.CharField(max_length=64, unique=True)
    map_name = models.CharField(max_length=64, blank=True)
    map_id = models.CharField(max_length=64, blank=True)
    mode = models.CharField(max_length=64, blank=True)
    queue_id = models.CharField(max_length=32, blank=True)
    season_id = models.CharField(max_length=32, blank=True)
    region = models.CharField(max_length=16, blank=True)
    platform = models.CharField(max_length=10, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=32, default="henrikdev")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["started_at"], name="idx_tracker_match_started"),
        ]

    def __str__(self):
        return self.match_id


class TrackerPlayerMatch(models.Model):
    """Rendimiento de un jugador concreto en una partida concreta."""

    class Result(models.TextChoices):
        VICTORY = "victory", "Victoria"
        DEFEAT = "defeat", "Derrota"
        DRAW = "draw", "Empate"
        UNKNOWN = "unknown", "Desconocido"

    # db_index=False: los índices se declaran explícitos en Meta para evitar
    # duplicarlos con los automáticos de la FK.
    player = models.ForeignKey(
        TrackerPlayer,
        on_delete=models.CASCADE,
        related_name="match_entries",
        db_index=False,
    )
    match = models.ForeignKey(
        TrackerMatch,
        on_delete=models.CASCADE,
        related_name="player_entries",
        db_index=False,
    )
    agent_name = models.CharField(max_length=64, blank=True)
    agent_id = models.CharField(max_length=64, blank=True)
    team_id = models.CharField(max_length=16, blank=True)
    result = models.CharField(
        max_length=8,
        choices=Result.choices,
        default=Result.UNKNOWN,
    )
    rounds_won = models.PositiveIntegerField(null=True, blank=True)
    rounds_lost = models.PositiveIntegerField(null=True, blank=True)
    kills = models.PositiveIntegerField(null=True, blank=True)
    deaths = models.PositiveIntegerField(null=True, blank=True)
    assists = models.PositiveIntegerField(null=True, blank=True)
    headshots = models.PositiveIntegerField(null=True, blank=True)
    bodyshots = models.PositiveIntegerField(null=True, blank=True)
    legshots = models.PositiveIntegerField(null=True, blank=True)
    damage_dealt = models.PositiveIntegerField(null=True, blank=True)
    damage_received = models.PositiveIntegerField(null=True, blank=True)
    combat_score = models.PositiveIntegerField(null=True, blank=True)
    rank_tier = models.PositiveSmallIntegerField(null=True, blank=True)
    source = models.CharField(max_length=32, default="henrikdev")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["player", "match"],
                name="uniq_tracker_player_match",
            ),
        ]
        indexes = [
            models.Index(fields=["player"], name="idx_tracker_pm_player"),
            models.Index(fields=["match"], name="idx_tracker_pm_match"),
        ]

    def __str__(self):
        return f"{self.player} @ {self.match.match_id}"
