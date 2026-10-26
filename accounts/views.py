from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import PatientRegistrationForm
from .models import Profile


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = None
    if request.method == 'POST':
        u = authenticate(username=request.POST.get('username'), password=request.POST.get('password'))
        if u:
            login(request, u)
            return redirect('dashboard')
        error = 'Invalid username or password.'
    return render(request, 'accounts/login.html', {'error': error})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = PatientRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        Profile.objects.create(
            user=user,
            role='PATIENT',
            organization='Federated Healthcare',
            client_id='',
        )
        messages.success(request, 'Patient account created successfully. You can now sign in.')
        return redirect('login')
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def dashboard(request):
    p = getattr(request.user, 'profile', None)
    if request.user.is_staff or (p and p.role == 'ADMIN'):
        return redirect('admin_dashboard')
    if p and p.role == 'HOSPITAL':
        return redirect('hospital_dashboard')
    return redirect('patient_dashboard')


def logout_view(request):
    logout(request)
    return redirect('login')
