import json
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

import pandas as pd
import numpy as np

from .models import Submission, FederatedRound, GlobalModel
from services.fl_service import train_local_model, LOCAL_TREES, EXPECTED_CLIENTS
from services.ml_service import model_info



# Feature names are taken from services.ml_service.FEATURES.
# Analytics are descriptive summaries only; they do not change model training.
def analyze_uploaded_dataset(uploaded_file):
    """Create privacy-conscious aggregate statistics for the hospital analytics UI."""
    from services.ml_service import FEATURES, NUMERICAL, CATEGORICAL

    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
        uploaded_file.seek(0)
    except Exception as exc:
        raise ValueError(f"Could not read the CSV file: {exc}")

    # Keep only feature columns that are present for descriptive analysis.
    present_features = [column for column in FEATURES if column in df.columns]
    missing_columns = [column for column in FEATURES + ['sublabel'] if column not in df.columns]

    def count_values(series):
        values = series.fillna("Missing").astype(str).str.strip()
        values = values.replace({"": "Missing", "nan": "Missing", "None": "Missing"})
        counts = values.value_counts(dropna=False)
        return {"labels": [str(x) for x in counts.index], "counts": [int(x) for x in counts.values]}

    def numeric_distribution(column, bins=10):
        if column not in df.columns:
            return {"labels": [], "counts": []}
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if series.empty:
            return {"labels": [], "counts": []}
        if series.nunique() <= 1:
            return {"labels": [str(round(float(series.iloc[0]), 2))], "counts": [int(len(series))]}
        try:
            cut = pd.cut(series, bins=min(bins, max(2, series.nunique())), include_lowest=True, duplicates="drop")
            counts = cut.value_counts(sort=False)
            return {
                "labels": [str(interval) for interval in counts.index],
                "counts": [int(value) for value in counts.values],
            }
        except Exception:
            return {"labels": [], "counts": []}

    def category_counts(column, mapping=None):
        if column not in df.columns:
            return {"labels": [], "counts": []}
        series = df[column].fillna("Missing").astype(str).str.strip()
        series = series.replace({"": "Missing", "nan": "Missing", "None": "Missing"})
        if mapping:
            series = series.map(lambda value: mapping.get(value.lower(), value) if value != "Missing" else value)
        counts = series.value_counts()
        return {"labels": [str(x) for x in counts.index], "counts": [int(x) for x in counts.values]}

    def age_groups():
        if "age" not in df.columns:
            return {"labels": [], "counts": []}
        age = pd.to_numeric(df["age"], errors="coerce")
        bins = [-float("inf"), 17, 29, 44, 59, float("inf")]
        labels = ["0–17", "18–29", "30–44", "45–59", "60+"]
        valid = age.notna() & age.ge(0)
        grouped = pd.cut(age[valid], bins=bins, labels=labels, right=True)
        counts = grouped.value_counts(sort=False)
        return {"labels": labels, "counts": [int(counts.get(label, 0)) for label in labels]}

    def age_gender():
        if "age" not in df.columns or "gender" not in df.columns:
            return {"labels": [], "datasets": []}
        age = pd.to_numeric(df["age"], errors="coerce")
        gender = df["gender"].fillna("Missing").astype(str).str.strip()
        gender = gender.replace({"": "Missing", "nan": "Missing"})
        valid = age.notna() & age.ge(0)
        bins = [-float("inf"), 17, 29, 44, 59, float("inf")]
        age_labels = ["0–17", "18–29", "30–44", "45–59", "60+"]
        frame = pd.DataFrame({"age": age[valid], "gender": gender[valid]})
        frame["age_group"] = pd.cut(frame["age"], bins=bins, labels=age_labels, right=True)
        genders = sorted(frame["gender"].unique().tolist())
        return {
            "labels": age_labels,
            "datasets": [
                {"label": str(g), "data": [int(((frame["age_group"] == group) & (frame["gender"] == g)).sum()) for group in age_labels]}
                for g in genders
            ],
        }

    def bmi_categories():
        if "bmi" not in df.columns:
            return {"labels": [], "counts": []}
        bmi = pd.to_numeric(df["bmi"], errors="coerce")
        # Adult BMI categories are used only as descriptive groupings; they are not a diagnosis.
        labels = ["Underweight (<18.5)", "Normal (18.5–24.9)", "Overweight (25–29.9)", "Obesity (≥30)", "Missing/invalid"]
        counts = [
            int((bmi < 18.5).sum()),
            int(((bmi >= 18.5) & (bmi < 25)).sum()),
            int(((bmi >= 25) & (bmi < 30)).sum()),
            int((bmi >= 30).sum()),
            int((bmi.isna() | (bmi <= 0)).sum()),
        ]
        # Avoid counting invalid/non-positive BMI in another category.
        counts[:4] = [
            int(((bmi > 0) & (bmi < 18.5)).sum()),
            int(((bmi >= 18.5) & (bmi < 25)).sum()),
            int(((bmi >= 25) & (bmi < 30)).sum()),
            int((bmi >= 30).sum()),
        ]
        return {"labels": labels, "counts": counts}

    def sleep_groups():
        if "sleep_hours" not in df.columns:
            return {"labels": [], "counts": []}
        values = pd.to_numeric(df["sleep_hours"], errors="coerce")
        labels = ["<6 hours", "6–8 hours", ">8 hours", "Missing/invalid"]
        return {"labels": labels, "counts": [
            int((values < 6).sum()),
            int(((values >= 6) & (values <= 8)).sum()),
            int((values > 8).sum()),
            int((values.isna() | (values <= 0)).sum()),
        ]}

    # Dataset-level quality summaries, computed on the raw uploaded CSV.
    total_rows = int(len(df))
    missing_cells = int(df[present_features].isna().sum().sum()) if present_features else 0
    blank_cells = 0
    if present_features:
        for column in present_features:
            if df[column].dtype == object:
                blank_cells += int(df[column].astype(str).str.strip().eq("").sum())
    required_present = [column for column in FEATURES if column in df.columns]
    complete_mask = df[required_present].notna().all(axis=1) if required_present else pd.Series([False] * len(df))
    if required_present:
        for column in required_present:
            if df[column].dtype == object:
                complete_mask &= df[column].astype(str).str.strip().ne("")
    complete_rows = int(complete_mask.sum()) if len(df) else 0

    negative_columns = ["age", "age_normalized", "bmi", "HbA1c_level", "glucose", "cholesterol",
                        "sleep_hours", "triglycerides", "blood_pressure", "crp_level",
                        "homocysteine_level", "systolic_bp", "diastolic_bp", "alcohol_intake",
                        "salt_intake", "heart_rate", "hdl", "ldl"]
    negative_values = {}
    for column in negative_columns:
        if column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce")
            count = int((values < 0).sum())
            if count:
                negative_values[column] = count

    duplicate_rows = int(df.duplicated().sum())
    class_data = category_counts("sublabel")

    # Numeric summaries for key measurements.
    numeric_summaries = {}
    for column in ["age", "bmi", "cholesterol", "sleep_hours", "HbA1c_level", "glucose",
                   "systolic_bp", "diastolic_bp", "heart_rate", "hdl", "ldl", "triglycerides"]:
        if column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce").dropna()
            numeric_summaries[column] = {
                "count": int(values.count()),
                "mean": round(float(values.mean()), 2) if not values.empty else None,
                "median": round(float(values.median()), 2) if not values.empty else None,
                "min": round(float(values.min()), 2) if not values.empty else None,
                "max": round(float(values.max()), 2) if not values.empty else None,
            }

    return {
        "total_rows": total_rows,
        "complete_rows": complete_rows,
        "missing_feature_cells": missing_cells + blank_cells,
        "missing_columns": missing_columns,
        "duplicate_rows": duplicate_rows,
        "negative_values": negative_values,
        "numeric_summaries": numeric_summaries,
        "age_groups": age_groups(),
        "age_gender": age_gender(),
        "gender": category_counts("gender"),
        "smoking": category_counts("smoking"),
        "employment": category_counts("employment_status"),
        "education": category_counts("education_level"),
        "physical_activity": category_counts("physical_activity"),
        "family_history": category_counts("family_history"),
        "stress_level": category_counts("stress_level"),
        "bmi_categories": bmi_categories(),
        "bmi_level": category_counts("bmi_level"),
        "sleep_groups": sleep_groups(),
        "cholesterol": numeric_distribution("cholesterol"),
        "glucose": numeric_distribution("glucose"),
        "hba1c": numeric_distribution("HbA1c_level"),
        "blood_pressure": numeric_distribution("blood_pressure"),
        "systolic_bp": numeric_distribution("systolic_bp"),
        "diastolic_bp": numeric_distribution("diastolic_bp"),
        "sublabel": class_data,
        "smoking_by_gender": _cross_tab(df, "smoking", "gender"),
        "bmi_by_age": _cross_bmi_age(df),
    }


def _cross_tab(df, row_column, column_column):
    if row_column not in df.columns or column_column not in df.columns:
        return {"labels": [], "datasets": []}
    frame = df[[row_column, column_column]].copy()
    for column in [row_column, column_column]:
        frame[column] = frame[column].fillna("Missing").astype(str).str.strip().replace({"": "Missing", "nan": "Missing"})
    table = pd.crosstab(frame[row_column], frame[column_column])
    return {
        "labels": [str(value) for value in table.index],
        "datasets": [
            {"label": str(column), "data": [int(value) for value in table[column].tolist()]}
            for column in table.columns
        ],
    }


def _cross_bmi_age(df):
    if "bmi" not in df.columns or "age" not in df.columns:
        return {"labels": [], "datasets": []}
    frame = pd.DataFrame({
        "age": pd.to_numeric(df["age"], errors="coerce"),
        "bmi": pd.to_numeric(df["bmi"], errors="coerce"),
    }).dropna()
    frame = frame[(frame["age"] >= 0) & (frame["bmi"] > 0)]
    if frame.empty:
        return {"labels": [], "datasets": []}
    age_labels = ["0–17", "18–29", "30–44", "45–59", "60+"]
    frame["age_group"] = pd.cut(frame["age"], [-float("inf"), 17, 29, 44, 59, float("inf")], labels=age_labels)
    frame["bmi_group"] = pd.cut(frame["bmi"], [0, 18.5, 25, 30, float("inf")],
                                labels=["Underweight", "Normal", "Overweight", "Obesity"], right=False)
    table = pd.crosstab(frame["age_group"], frame["bmi_group"]).reindex(age_labels, fill_value=0)
    return {
        "labels": age_labels,
        "datasets": [
            {"label": str(column), "data": [int(value) for value in table[column].tolist()]}
            for column in table.columns
        ],
    }


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
    analytics = None

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

                # Analyze the uploaded CSV for descriptive charts, then rewind it
                # so the existing local-training service reads the full file.
                analytics = analyze_uploaded_dataset(f)
                f.seek(0)

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
            'analytics': analytics,
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