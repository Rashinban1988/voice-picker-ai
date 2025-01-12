from django.shortcuts import render

def job_seeker_index_for_company(request):
    print("job_seeker_index_for_company")
    return render(request, 'job_seekers/index.html')
