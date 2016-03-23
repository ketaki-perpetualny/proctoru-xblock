import datetime
import dateutil.parser
import pytz
import random
import requests
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from .models import ProctoruUser, ProctorUAuthToken, ProctorUExam

from .timezonemap import win_tz


API_URLS = {
    "get_time_zone": "https://y.proctoru.com/api/getTimeZoneList",
    "get_sche_info_avl_time_list": "https://y.proctoru.com/api/getScheduleInfoAvailableTimesList",
    "add_adhoc_process": "https://y.proctoru.com/api/addAdHocProcess",
    "remove_reservation": "https://y.proctoru.com/api/removeReservation",
    "client_activity_report": "https://y.proctoru.com/api/clientActivityReport",
    "pending_exam_report": "https://y.proctoru.com/api/pendingExamReport",
}


class ProctoruAPI():

    def create_user(self, user_id, post_data):
        try:
            user = User.objects.get(pk=user_id)
            proctoru_user = ProctoruUser(student=user,
                                         phone_number=str(
                                             post_data.get('phone'))[:15],
                                         time_zone=post_data.get(
                                             'time_zone')[:60],
                                         address=post_data.get(
                                             'address')[:100],
                                         city=post_data.get('city')[:50],
                                         country=post_data.get('country')[:2],
                                         state="CA",
                                         )
            proctoru_user.save()
            return {"status": "success"}
        except:
            return {"status": "error"}

    def get_user_first_name(self, user):
        if user.profile.name != '':
            return user.profile.name
        else:
            return user.username

    def get_user_last_name(self, user):
        if user.last_name != '':
            return user.first_name
        else:
            return ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for i in range(8))

    def get_user(self, user_id):
        try:
            user = ProctoruUser.objects.get(student=user_id)
            user_data = {
                'username': user.student.username,
                'first_name': self.get_user_first_name(user.student),
                'last_name': self.get_user_last_name(user.student),
                'email': user.student.email,
                'id': user.student.id,
                'is_active': user.student.is_active,
                'is_superuser': user.student.is_superuser,
                'is_staff': user.student.is_staff,
                'phone_number': user.phone_number,
                'city': user.city,
                'country': user.country,
                'time_zone': user.time_zone,
                'address': user.address,
                'state': user.state,
            }
            return user_data
        except:
            return None

    def auth_token(self):
        """
        This will return the auth token from model
        """
        try:
            token = ProctorUAuthToken.objects.filter(enabled=True)[0]

            return {
                "Authorization-Token": token.token,
            }
        except:
            return {
                "error": "not found", }

    def get_time_zones(self):
        """
        Get time zones by calling getTimeZoneList of ProctorU.
        """
        data = {
            "time_sent": datetime.datetime.utcnow().isoformat()
        }
        response = requests.get(
            API_URLS.get('get_time_zone'), data=data, headers=self.auth_token())
        return response.json()

    def is_user_created(self, user_id):
        try:
            ProctoruUser.objects.get(student=user_id)
            return True
        except:
            return False

    def get_schedule_info_avl_timeslist(self, data=None):
        """
        Get getscheduleavailabletimeslist.
        """
        response = requests.get(
            API_URLS.get('get_sche_info_avl_time_list'),
            data=data,
            headers=self.auth_token()
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "InvalidResponse"}

    def render_shedule_ui(self, user_id, time_details, duration):
        """
        Render shedule ui.
        """
        try:
            pr_user = ProctoruUser.objects.get(student=user_id)
        except ObjectDoesNotExist:
            return {"status": "error"}

        api_exam_start_time = time_details.get("api_exam_start_time")

        offset_time = self.get_ramaining_countdown(
            api_exam_start_time.isoformat(), pr_user)

        if api_exam_start_time:
            data = {
                "time_sent": time_details.get("time_stamp"),
                'duration': duration,
                'time_zone_id': pr_user.time_zone,
                'start_date': offset_time,
                'takeitnow': 'N',
                'isadhoc': 'Y'
            }
            avl_date_time_list_json = self.get_schedule_info_avl_timeslist(
                data)

            status = avl_date_time_list_json.get('status', None)

            if status == "InvalidResponse":
                return {"status": "error"}
            elif avl_date_time_list_json.get("response_code") == 1:
                avl_date_time_list = avl_date_time_list_json.get(
                    'data',
                    None)

                context = self.return_context_render_shedule(
                    avl_date_time_list,
                    pr_user,
                    time_details
                )
                return context
            else:
                return {'status': "error"}
        else:
            return {'status': "error"}

    def get_time_list_for_specific_date(self, selected_date, available_time_list):
        """
        Return list of available time for a specific date.

        format.
        """
        time_list = [available_time for available_time in available_time_list if available_time.date(
        ) == selected_date.date()]

        return time_list

    def get_time_details_api(self, time_details, user_selected_date=None, user_id=None):
        """
        Returns the time details required for apis
        """

        exam_start_date_time = time_details.get('exam_start_date_time')

        exam_start_date_time = dateutil.parser.parse(
            exam_start_date_time)

        exam_end_date_time = time_details.get('exam_end_date_time')

        exam_end_date_time = dateutil.parser.parse(
            exam_end_date_time)

        time_stamp = datetime.datetime.utcnow().isoformat()

        current_date = datetime.datetime.utcnow()

        current_date = current_date.replace(tzinfo=pytz.utc)

        if current_date <= exam_end_date_time:
            # Check if start date is in past
            if exam_start_date_time <= current_date:
                str_exam_start_date_time = current_date

            elif exam_start_date_time > current_date:
                str_exam_start_date_time = exam_start_date_time

            str_exam_end_date_time = exam_end_date_time

            if user_selected_date:
                dt = datetime.datetime.strptime(
                    '{0} 00:00'.format(user_selected_date), '%m/%d/%Y %H:%M')

                api_exam_start_time = dt.replace(tzinfo=pytz.utc)

                if api_exam_start_time < current_date:
                    api_exam_start_time = current_date

            elif exam_start_date_time > current_date:
                api_exam_start_time = exam_start_date_time
            else:
                api_exam_start_time = current_date

            api_exam_start_time = datetime.datetime(
                api_exam_start_time.year,
                api_exam_start_time.month,
                api_exam_start_time.day,
                tzinfo=pytz.utc)

            time_details = {
                'time_stamp': time_stamp,
                'exam_start_time': exam_start_date_time,
                'str_exam_start_date': str_exam_start_date_time,
                'api_exam_start_time': api_exam_start_time,
                'exam_end_date_time': exam_end_date_time,
                'str_exam_end_date': str_exam_end_date_time,
                'status': 'examdateavailable',
            }

            return time_details
        else:
            return {'status': 'examdatepass'}

    def add_adhoc_process(self, student_data):
        """
        AddAdHocProcess.
        """
        data = student_data
        response = requests.post(
            API_URLS.get('add_adhoc_process'), data=data, headers=self.auth_token())
        return response.json()

    def set_exam_schedule_arrived(self, exam_data):
        """
        Schedule exam.
        """
        try:
            # Delete all previous exams
            old_exams = ProctorUExam.objects.filter(
                user=exam_data.get('user'), course_id=exam_data.get('course_id'))
            old_exams.delete()
            exam = ProctorUExam(**exam_data)
            exam.save()
            return True
        except:
            return False

    def end_exam(self, student, course_id):
        """
        end exam.
        """
        try:
            old_exam = ProctorUExam.objects.get(
                user=student, course_id=course_id)
            old_exam.is_completed = True
            old_exam.is_started = False
            old_exam.end_time = datetime.datetime.utcnow()
            old_exam.save()
            return True
        except:
            return False

    def start_exam(self, student, course_id):
        """
        end exam.
        """
        try:
            old_exam = ProctorUExam.objects.get(
                user=student, course_id=course_id)
            old_exam.is_completed = False
            old_exam.is_started = True
            old_exam.actual_start_time = datetime.datetime.utcnow()
            old_exam.save()
            return True
        except:
            return False

    def get_schedule_exam_arrived(self, user, course_id):
        """
        get schedule exam details.

        user = User object
        course_id = Course number(string)

        """
        try:
            exam = ProctorUExam.objects.get(user=user, course_id=course_id)
            return exam
        except:
            return None

    def cancel_exam(self, user, course_id):
        """
        cancel exam

        user = User object
        course_id = Course number(string)

        """
        try:
            exam = ProctorUExam.objects.get(user=user, course_id=course_id)
            time_stamp = datetime.datetime.utcnow().isoformat()
            data = {
                "time_sent": time_stamp,
                "student_id": user.id,
                "reservation_no": exam.reservation_no,
            }
            response_data = requests.post(
                API_URLS.get('remove_reservation'), data=data, headers=self.auth_token()).json()
            exam.is_canceled = True
            exam.save()
            return response_data
        except:
            return None

    def get_student_activity(self, user_id, course_key, start_date, end_date):
        """
        This resource returns an activity report of reservations on the ProctorU website for a specified date range or test-taker.
        user = user id
        start_date =  exam start date
        end_date =  exam end date
        """
        try:
            exam = ProctorUExam.objects.get(
                user_id=user_id, course_id=course_key)
            time_stamp = datetime.datetime.utcnow().isoformat()
            data = {
                "time_sent": time_stamp,
                "student_id": user_id,
                "end_date": end_date,
                "start_date": start_date,
            }
            response_data = requests.post(
                API_URLS.get('client_activity_report'), data=data, headers=self.auth_token()).json()
            for data_new in response_data.get('data'):
                if int(data_new.get("ReservationNo")) == int(exam.reservation_no):
                    data_new["StartDate"] = self.get_formated_exam_dates(
                        data_new["StartDate"], user_id)
                    data_new["EndDate"] = self.get_formated_exam_dates(
                        data_new["EndDate"], user_id)
                    return data_new
            return None
        except:
            return None

    def get_student_sessions(self, course_id):
        """
        get student sessions.

        course_id = Course number(string)

        """
        exam = ProctorUExam.objects.filter(course_id=course_id)
        return exam

    def get_formated_exam_start_date(self, exam_date, user_id):
        """
        return heading for exam time
        """
        try:
            pr_user = ProctoruUser.objects.get(student=user_id)
        except ObjectDoesNotExist:
            pass

        exam_datetime_obj = dateutil.parser.parse(
            exam_date)

        first_heading = "{0} {1}".format(
            exam_datetime_obj.strftime("%I:%M %p"), pr_user.time_zone
        )

        second_heading = exam_datetime_obj.strftime("%A %B %dth, %Y")

        return {
            "first_heading": first_heading,
            "second_heading": second_heading,
        }


    def get_utc_offset(self, dt, tm):
        dm = dt.strftime('%z')
        if 'Z' in tm:
            tm = '{0}{1}:{2}'.format(tm[:-1], dm[:3], dm[3:])
        else:
            tm = '{0}{1}:{2}'.format(tm[:-6], dm[:3], dm[3:])
        return tm


    def get_formated_exam_dates(self, exam_date, user_id):
        """
        return heading for exam time
        """
        try:
            pr_user = ProctoruUser.objects.get(student=user_id)
        except ObjectDoesNotExist:
            pass

        #tzobj = pytz.timezone(win_tz[pr_user.time_zone])

        #utcmoment_unaware = datetime.datetime.utcnow()

        #utcmoment = utcmoment_unaware.replace(
        #    tzinfo=pytz.utc).astimezone(tzobj)

        #exam_date = self.get_utc_offset(utcmoment, exam_date)

        #exam_datetime_obj = dateutil.parser.parse(exam_date) #.astimezone(tzobj)

        #date = "{0} {1}".format(
        #    exam_datetime_obj.strftime("%A %B %dth, %Y %I:%M %p"), pr_user.time_zone)
        return exam_date

    def return_context_render_shedule(
            self,
            avl_date_time_list, pr_user, time_details):
        """
        return context for shedule ui
        """
        api_exam_start_time = time_details.get("api_exam_start_time")
        exam_start_date_time = time_details.get("exam_start_time")
        exam_end_date_time = time_details.get("exam_end_date_time")
        staff_time_zone = time_details.get("staff_time_zone")

        str_exam_start_date = time_details.get('str_exam_start_date')

        str_exam_end_date = time_details.get('str_exam_end_date')

        tzobj = pytz.timezone(win_tz[pr_user.time_zone])

        str_exam_start_date = str_exam_start_date.astimezone(tzobj).strftime(
            "%m/%d/%Y")

        str_exam_end_date = str_exam_end_date.astimezone(tzobj).strftime(
            "%m/%d/%Y")

        first_date_available = "{0} {1}".format(exam_start_date_time.strftime(
            "%A %B %dth %Y %I:%M %p"), staff_time_zone)
        last_date_available = "{0} {1}".format(exam_end_date_time.strftime(
            "%A %B %dth %Y %I:%M %p"), staff_time_zone)

        date_time_obj_list = []

        for available_time in avl_date_time_list:

            dt_obj = dateutil.parser.parse(available_time.get(
                'local_start_date', None)
            )

            retrived_date = dateutil.parser.parse(self.getexamtime_staff(
                dt_obj.isoformat(),
                tzobj)
            )

            if exam_start_date_time <= retrived_date <= exam_end_date_time:
                date_time_obj_list.append(dt_obj)

        if date_time_obj_list:

            time_list = date_time_obj_list

            if time_list:
                available_times_for_day = []

                for available_time in time_list:
                    time_slot_info = {
                        'time_utc': "{0} {1}".format(available_time.strftime(
                            "%I:%M %p"), pr_user.time_zone),
                        'day_year': available_time.strftime(
                            "%A %B %dth, %Y"),
                        'data_value': available_time.isoformat()
                    }
                    available_times_for_day.append(time_slot_info)
                context = {
                    'time_list': available_times_for_day,
                    'first_date_available': first_date_available,
                    'last_date_available': last_date_available,
                    'start_date': str_exam_start_date,
                    'end_date': str_exam_end_date,
                    'selected_date': api_exam_start_time.strftime(
                        "%m/%d/%Y"),
                    'status': 'available_list'
                }
                return context

        context = {
            'time_list': [],
            'first_date_available': first_date_available,
            'last_date_available': last_date_available,
            'start_date': str_exam_start_date,
            'end_date': str_exam_end_date,
            'selected_date': api_exam_start_time.strftime(
                "%m/%d/%Y"),
            'status': 'emptylist'
        }
        return context

    def get_ramaining_countdown(self, tm, user):
        try:
            tzobj = pytz.timezone(win_tz[user.time_zone])
            dt = dateutil.parser.parse(tm).astimezone(tzobj)
            tm = self.get_utc_offset(dt, tm)
            return tm
        except:
            return False

    def getexamtime_staff(self, tm, timezone):
        try:
            tzobj = timezone
            dt = dateutil.parser.parse(tm).astimezone(tzobj)
            tm = self.get_utc_offset(dt, tm)
            return tm
        except:
            return False

    def get_pending_exam_report(self, user_id):
        """
        This resource returns a report of pending exams on the ProctorU website for a specific test taker.
        If no test taker is specified, all pending exams for the institution will be returned.
        """
        try:
            time_stamp = datetime.datetime.utcnow().isoformat()
            data = {
                "time_sent": time_stamp,
                "student_id": user_id,
            }
            response_data = requests.post(
                API_URLS.get('pending_exam_report'), data=data, headers=self.auth_token()).json()
            return response_data
        except:
            return None
