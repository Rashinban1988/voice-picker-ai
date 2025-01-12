from django.urls import path
from .views import job_seeker_index_for_company

urlpatterns = [
    path('', job_seeker_index_for_company, name='job_seeker_index_for_company'),
]