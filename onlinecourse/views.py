from django.shortcuts import render
from django.http import HttpResponseRedirect
# <HINT> Import any new Models here
from .models import Course, Enrollment, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging
# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        # Check if user exists
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name,
                                            password=password)
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:
        # Check if user enrolled
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_details_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        # Create an enrollment
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))

def submit(request, course_id):
    course = get_object_or_404(Course, pk=course_id)

    if request.method == 'POST' and request.user.is_authenticated:
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course=course
        )

        submission = Submission.objects.create(enrollment=enrollment)

        selected_ids = []

        for key, value in request.POST.items():
            if key.startswith('choice_'):
                selected_ids.append(int(value))

        selected_choices = Choice.objects.filter(
            id__in=selected_ids,
            question__lesson__course=course
        )

        submission.choices.set(selected_choices)

        return redirect(
            'onlinecourse:show_exam_result',
            course_id=course.id,
            submission_id=submission.id
        )

    return redirect('onlinecourse:course_details', pk=course.id)


def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__user=request.user,
        enrollment__course=course
    )

    selected_ids = set(
        submission.choices.values_list('id', flat=True)
    )

    questions = Question.objects.filter(lesson__course=course)

    total_score = 0
    total_possible = 0
    results = []

    for question in questions:
        correct_ids = set(
            question.choice_set.filter(
                is_correct=True
            ).values_list('id', flat=True)
        )

        question_selected_ids = set(
            question.choice_set.filter(
                id__in=selected_ids
            ).values_list('id', flat=True)
        )

        is_correct = (
            question_selected_ids == correct_ids
            and len(correct_ids) > 0
        )

        total_possible += question.grade

        if is_correct:
            total_score += question.grade

        results.append({
            'question': question,
            'choices': question.choice_set.all(),
            'selected_ids': question_selected_ids,
            'correct_ids': correct_ids,
            'is_correct': is_correct,
        })

    if total_possible > 0:
        grade = (total_score / total_possible) * 100
    else:
        grade = 0

    submission.total_score = total_score
    submission.save()

    context = {
        'course': course,
        'submission': submission,
        'grade': grade,
        'total_score': total_score,
        'total_possible': total_possible,
        'results': results,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )


