"""URL configuration for test_project."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("calculate/<int:a>/<int:b>/", views.calculate_view, name="calculate"),
    path("variables/", views.variable_inspection_view, name="variables"),
]
