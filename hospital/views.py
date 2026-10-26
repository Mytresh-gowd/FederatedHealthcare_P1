import json
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .models import Submission, FederatedRound, GlobalModel
from services.fl_service import train_local_model, LOCAL_TREES, EXPECTED_CLIENTS
from services.ml_service import model_info


def hospital_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        p = getattr(request.user, 'profile', None)

        if (
            not request.user.is_authenticated
            or not p
            or p.role != 'HOSPITAL'
        ):
            return redirect('login')

        return view(request, *args, **kwargs)

    return wrapped


@login_required
@hospital_only
def dashboard(request):
    items = Submission.objects.filter(
        hospital=request.user
    ).order_by('-created_at')

    last = items.first()

    active = GlobalModel.objects.filter(
        status='ACTIVE'
    ).first()

    current_round = FederatedRound.objects.filter(
        status='OPEN'
    ).order_by('-round_no').first()

    return render(
        request,
        'hospital/dashboard.html',
        {
            'items': items,
            'last': last,
            'active': active,
            'profile': request.user.profile,
            'current_round': current_round,
            'local_trees': LOCAL_TREES,
            'expected_clients': EXPECTED_CLIENTS,
        }
    )


@login_required
@hospital_only
def upload(request):
    metric = None
    error = None

    current_round = FederatedRound.objects.filter(
        status='OPEN'
    ).order_by('-round_no').first()

    if request.method == 'POST':
        f = request.FILES.get('dataset')

        if not f:
            error = 'Please choose a CSV dataset.'

        elif not f.name.lower().endswith('.csv'):
            error = 'Only CSV files are supported in Phase 1.'

        else:
            try:
                if not current_round:
                    last_round = FederatedRound.objects.order_by(
                        '-round_no'
                    ).first()

                    next_round_no = (
                        last_round.round_no + 1
                        if last_round
                        else 1
                    )

                    current_round = FederatedRound.objects.create(
                        round_no=next_round_no
                    )

                profile = request.user.profile

                result = train_local_model(
                    f,
                    profile.client_id or request.user.username,
                    current_round.round_no
                )

                sub = (
                    Submission.objects
                    .filter(
                        hospital=request.user,
                        round_no=current_round.round_no
                    )
                    .exclude(status='AGGREGATED')
                    .order_by('-created_at')
                    .first()
                )

                if sub is None:
                    sub = Submission(
                        hospital=request.user,
                        round_no=current_round.round_no
                    )

                sub.filename = f.name
                sub.records = result['records']
                sub.train_rows = result['train_rows']
                sub.validation_rows = result['validation_rows']
                sub.test_rows = result['test_rows']
                sub.class_distribution = result['class_distribution']
                sub.accuracy = result['accuracy']
                sub.macro_f1 = result['macro_f1']
                sub.trees = result['trees']
                sub.status = 'TRAINED'
                sub.artifact_path = result['path']
                sub.save()

                metric = sub

                messages.success(
                    request,
                    f'Local model trained for Round '
                    f'{current_round.round_no}. '
                    'Review the dataset summary and submit the model.'
                )

            except Exception as exc:
                error = str(exc)

    # Prepare chart data for the upload page.
    chart_labels = []
    chart_counts = []
    chart_percentages = []

    if metric and isinstance(metric.class_distribution, dict):
        valid_items = []

        for label, count in metric.class_distribution.items():
            try:
                count = int(count)

                if count >= 0:
                    valid_items.append((str(label), count))

            except (TypeError, ValueError):
                continue

        valid_items.sort(key=lambda entry: entry[1], reverse=True)

        total = sum(count for _, count in valid_items)

        for label, count in valid_items:
            chart_labels.append(label)
            chart_counts.append(count)
            chart_percentages.append(
                round(count * 100 / total, 2) if total else 0
            )

    return render(
        request,
        'hospital/upload.html',
        {
            'metric': metric,
            'error': error,
            'round': current_round,
            'local_trees': LOCAL_TREES,
            'model': model_info(),
            'chart_labels': chart_labels,
            'chart_counts': chart_counts,
            'chart_percentages': chart_percentages,
            'class_count': len(chart_labels),
        }
    )


@login_required
@hospital_only
def submit(request, submission_id):
    if request.method != 'POST':
        return redirect('hospital_dashboard')

    sub = get_object_or_404(
        Submission,
        id=submission_id,
        hospital=request.user
    )

    if sub.status != 'TRAINED':
        messages.error(
            request,
            'Only a newly trained local model can be submitted.'
        )
        return redirect('hospital_dashboard')

    sub.status = 'SUBMITTED'
    sub.submitted_at = timezone.now()
    sub.save(update_fields=['status', 'submitted_at'])

    messages.success(
        request,
        f'{sub.filename} was submitted to the federated round.'
    )

    return redirect('hospital_dashboard')


@login_required
@hospital_only
def history(request):
    items = Submission.objects.filter(
        hospital=request.user
    ).order_by('-created_at')

    history_charts = []

    for item in items:
        distribution = item.class_distribution or {}

        if not isinstance(distribution, dict):
            distribution = {}

        valid_items = []

        for label, count in distribution.items():
            try:
                count = int(count)

                if count >= 0:
                    valid_items.append((str(label), count))

            except (TypeError, ValueError):
                continue

        valid_items.sort(key=lambda entry: entry[1], reverse=True)

        total = sum(count for _, count in valid_items)

        labels = [label for label, _ in valid_items]
        counts = [count for _, count in valid_items]

        percentages = [
            round(count * 100 / total, 2) if total else 0
            for count in counts
        ]

        # Prepare rows for the sublabel table.
        class_rows = []

        for label, count in valid_items:
            percentage = (
                round(count * 100 / total, 2) if total else 0
            )

            class_rows.append({
                'label': label,
                'count': count,
                'percentage': percentage,
            })

        # json_script safely embeds this data in the HTML template.
        chart_data = {
            'labels': labels,
            'counts': counts,
            'percentages': percentages,
        }

        history_charts.append({
            'item': item,
            'class_count': len(labels),
            'class_rows': class_rows,
            'chart_data': chart_data,
            'chart_data_id': f'history-chart-data-{item.id}',
            'bar_chart_id': f'history-bar-chart-{item.id}',
            'doughnut_chart_id': f'history-doughnut-chart-{item.id}',
        })

    return render(
        request,
        'hospital/history.html',
        {
            'items': items,
            'history_charts': history_charts,
        }
    )


@login_required
@hospital_only
def detail(request, submission_id):
    item = get_object_or_404(
        Submission,
        id=submission_id,
        hospital=request.user
    )

    return render(
        request,
        'hospital/detail.html',
        {'item': item}
    )