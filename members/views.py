from django.shortcuts import render, redirect
from .models import AddMemberForm, Member, SearchForm, UpdateMemberGymForm, UpdateMemberInfoForm
import datetime, csv
from django.http import HttpResponse
import dateutil.relativedelta as delta
import dateutil.parser as parser
from django.core.files.storage import FileSystemStorage
from payments.models import Payments
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from notifications.config import get_notification_count
from django.db.models.signals import post_save
from notifications.config import my_handler
from django.contrib import messages
from django.core.mail import send_mail


def model_save(model):
    post_save.disconnect(my_handler, sender=Member)
    model.save()
    post_save.connect(my_handler, sender=Member)

def check_status(request, object):
    object.stop = 1 if request.POST.get('stop') == '1' else 0
    return object

# Export user information.
def export_all(user_obj):
    response = HttpResponse(content_type='text/csv')
    writer = csv.writer(response)
    writer.writerow(['First name', 'Last name', 'Mobile', 'Admission Date', 'Subscription Type', 'Batch'])
    members = user_obj.values_list('first_name', 'last_name', 'mobile_number', 'admitted_on', 'subscription_type', 'batch')
    for user in members:
        first_name = user[0]
        last_name = user[1]
        writer.writerow(user)

    response['Content-Disposition'] = 'attachment; filename="' + first_name + ' ' + last_name + '.csv"'
    return response

def members(request):
    form = AddMemberForm()
    context = {
        'form': form,
        'subs_end_today_count': get_notification_count(),
    }
    return render(request, 'add_member.html', context)

def view_member(request):
    view_all = Member.objects.filter(stop=0).order_by('first_name')
    paginator = Paginator(view_all, 100)
    try:
        page = request.GET.get('page', 1)
        view_all = paginator.page(page)
    except PageNotAnInteger:
        view_all = paginator.page(1)
    except EmptyPage:
        view_all = paginator.page(paginator.num_pages)
    search_form = SearchForm()
    # get all members according to their batches
    evening = Member.objects.filter(batch='evening', stop=0).order_by('first_name')
    morning = Member.objects.filter(batch='morning', stop=0).order_by('first_name')
    stopped = Member.objects.filter(stop=1).order_by('first_name')
    context = {
        'all': view_all,
        'morning': morning,
        'evening': evening,
        'stopped': stopped,
        'search_form': search_form,
        'subs_end_today_count': get_notification_count(),
    }
    return render(request, 'view_member.html', context)

def add_member(request):
    view_all = Member.objects.all()
    success = 0
    member = None
    if request.method == 'POST':
        form = AddMemberForm(request.POST, request.FILES)
        if form.is_valid():
            # sending email notification when member registered
            first_name = request.POST['first_name']
            email = request.POST['email']
            last_name = request.POST['last_name']
            mobile_number = request.POST['mobile_number']
            address = request.POST['address']
            registration_date = request.POST['registration_date']
            subscription_type = request.POST['subscription_type']
            subscription_period = request.POST['subscription_period']
            batch = request.POST['batch']
            amount = request.POST['amount'] 
            subject = 'Welcome to our Gym!'
            message = f'Dear {first_name}, \n\n You have been registered to our Gym.\n Your datas: \n First Name: {first_name}\n Last Name: {last_name}\n Address: {address}\n Mobile Number: {mobile_number}\n Subscription Period: {subscription_period}\n Registration Date: {registration_date}\n Batch: {batch}\n Subscription type: {subscription_type}\n Amount:  ???{amount} \n\n We will help you to reach your achievements with us.\n Best regards,'
            from_email = 'aleksi1.deda@gmail.com'
            recipient_list = [email]
            send_mail(subject, message, from_email, recipient_list, fail_silently=False)

            temp = form.save(commit=False)
            temp.first_name = request.POST.get('first_name').capitalize()
            temp.last_name = request.POST.get('last_name').capitalize()
            temp.registration_upto = parser.parse(request.POST.get('registration_date')) + delta.relativedelta(months=int(request.POST.get('subscription_period')))
            if request.POST.get('fee_status') == 'pending':
                temp.notification = 1

            model_save(temp)
            success = 'Successfully Added Member'

            # Add payments if payment is 'paid'
            if temp.fee_status == 'paid':
                payments = Payments(
                                    user=temp,
                                    payment_date=temp.registration_date,
                                    payment_period=temp.subscription_period,
                                    payment_amount=temp.amount)
                payments.save()

            form = AddMemberForm()
            member = Member.objects.last()

        context = {
            'add_success': success,
            'form': form,
            'member': member,
            'subs_end_today_count': get_notification_count(),
        }
        return render(request, 'add_member.html', context)
    else:
        form = AddMemberForm()
        context = {
            'form': form,
            'subs_end_today_count': get_notification_count(),
        }
    return render(request, 'add_member.html', context)

def search_member(request):
    if request.method == 'POST':
        
        if 'clear' in request.POST:
            return redirect('view_member')
        search_form = SearchForm(request.POST)
        result = 0
        if search_form.is_valid():
            first_name = request.POST.get('search')
            result = Member.objects.filter(first_name__contains=first_name)

        view_all = Member.objects.all()
        # get all members according to their batches
        evening = Member.objects.filter(batch='evening')
        morning = Member.objects.filter(batch='morning')

        context = {
            'all': view_all,
            'morning': morning,
            'evening': evening,
            'search_form': search_form,
            'result': result,
            'subs_end_today_count': get_notification_count(),
        }
        return render(request, 'view_member.html', context)
    else:
        search_form = SearchForm()
    return render(request, 'view_member.html', {'search_form': search_form})

def delete_member(request, id):
    print(id)
    Member.objects.filter(pk=id).delete()
    return redirect('view_member')

def update_member(request, id):
    if request.method == 'POST' and request.POST.get('export'):
        return export_all(Member.objects.filter(pk=id))
    if request.method == 'POST' and request.POST.get('no'):
        return redirect('/')
    if request.method == 'POST' and request.POST.get('gym_membership'):
            gym_form = UpdateMemberGymForm(request.POST)
            if gym_form.is_valid():
                member = Member.objects.get(pk=id)
                amount = request.POST.get('amount')
                
                
                
                # if status is stopped then do not update anything
                if member.stop == 1 and not request.POST.get('stop') == '0' and request.POST.get('gym_membership'):
                    messages.error(request, 'Please start the status of user to update the record')
                    return redirect('update_member', id=member.pk)
               
                # to change only the batch
                elif (member.batch != request.POST.get('batch')):
                    member.batch = request.POST.get('batch')
                    member = check_status(request, member)
                    model_save(member)
                
                # check if user has modified only the date
                elif (datetime.datetime.strptime(str(member.registration_date), "%Y-%m-%d") != datetime.datetime.strptime(request.POST.get('registration_date'), "%Y-%m-%d")):
                        member.registration_date =  parser.parse(request.POST.get('registration_date'))
                        member.registration_upto =  parser.parse(request.POST.get('registration_date')) + delta.relativedelta(months=int(request.POST.get('subscription_period')))
                        member.fee_status = request.POST.get('fee_status')
                        member = check_status(request, member)
                        model_save(member)
               
                # if amount and period are changed
                elif (member.amount != amount) and (member.subscription_period != request.POST.get('subscription_period')):
                    member.subscription_type =  request.POST.get('subscription_type')
                    member.subscription_period =  request.POST.get('subscription_period')
                    member.registration_date =  parser.parse(request.POST.get('registration_upto'))
                    member.registration_upto =  parser.parse(request.POST.get('registration_upto')) + delta.relativedelta(months=int(request.POST.get('subscription_period')))
                    member.fee_status = request.POST.get('fee_status')
                    member.amount =  request.POST.get('amount')
                    member = check_status(request, member)
                    model_save(member)
               
                # if only subscription_period is Changed
                elif (member.subscription_period != request.POST.get('subscription_period')):
                    member.subscription_period =  request.POST.get('subscription_period')
                    member = check_status(request, member)
                    model_save(member)
               
                # if amount and type are changed
                elif (member.amount != amount) and (member.subscription_type != request.POST.get('subscription_type')):
                    member.subscription_type =  request.POST.get('subscription_type')
                    member.subscription_period =  request.POST.get('subscription_period')
                    member.registration_date =  parser.parse(request.POST.get('registration_upto'))
                    member.registration_upto =  parser.parse(request.POST.get('registration_upto')) + delta.relativedelta(months=int(request.POST.get('subscription_period')))
                    member.fee_status = request.POST.get('fee_status')
                    member.amount =  request.POST.get('amount')
                    member = check_status(request, member)
                    model_save(member)
                
                # if amount and fee status are changed
                elif (member.amount != amount) and ((request.POST.get('fee_status') == 'paid') or (request.POST.get('fee_status') == 'pending')):
                        member.amount = amount
                        member.fee_status = request.POST.get('fee_status')
                        member = check_status(request, member)
                        model_save(member)
                
                # if only amount is channged
                elif (member.amount != amount):
                    member.registration_date =  parser.parse(request.POST.get('registration_upto'))
                    member.registration_upto =  parser.parse(request.POST.get('registration_upto')) + delta.relativedelta(months=int(request.POST.get('subscription_period')))
                    member.fee_status = request.POST.get('fee_status')
                    member.amount =  request.POST.get('amount')
                    if request.POST.get('fee_status') == 'pending':
                        member.notification =  1
                    elif request.POST.get('fee_status') == 'paid':
                        member.notification = 2
                    member = check_status(request, member)
                    model_save(member)
                
                # nothing is changed
                else:
                    if not request.POST.get('stop') == '1':
                        member.registration_date =  parser.parse(request.POST.get('registration_upto'))
                        member.registration_upto =  parser.parse(request.POST.get('registration_upto')) + delta.relativedelta(months=int(request.POST.get('subscription_period')))
                        member.amount =  request.POST.get('amount')
                        if request.POST.get('fee_status') == 'pending':
                            member.notification =  1
                        elif request.POST.get('fee_status') == 'paid':
                            member.notification = 2
                    member.fee_status = request.POST.get('fee_status')
                    member = check_status(request, member)
                    model_save(member)

                # Add payments if payment is 'paid'
                if member.fee_status == 'paid':
                    check = Payments.objects.filter(
                        payment_date=member.registration_date,
                        user__pk=member.pk).count()
                    if check == 0:
                        payments = Payments(
                                            user=member,
                                            payment_date=member.registration_date,
                                            payment_period=member.subscription_period,
                                            payment_amount=member.amount)
                        payments.save()
                user = Member.objects.get(pk=id)
                gym_form = UpdateMemberGymForm(initial={
                                        'registration_date': user.registration_date,
                                        'registration_upto': user.registration_upto,
                                        'subscription_type': user.subscription_type,
                                        'subscription_period': user.subscription_period,
                                        'amount': user.amount,
                                        'fee_status': user.fee_status,
                                        'batch': user.batch,
                                        'stop': user.stop,
                                        })

                info_form = UpdateMemberInfoForm(initial={
                                        'first_name': user.first_name,
                                        'last_name': user.last_name,
                                        'dob': user.dob,
                                        })

                try:
                    payments = Payments.objects.filter(user=user)
                except Payments.DoesNotExist:
                    payments = 'No Records'
                messages.success(request, 'Record updated successfully!')
                return redirect('update_member', id=user.pk)
            else:
                user = Member.objects.get(pk=id)
                info_form = UpdateMemberInfoForm(initial={
                                        'first_name': user.first_name,
                                        'last_name': user.last_name,
                                        'dob': user.dob,
                                        })

                try:
                    payments = Payments.objects.filter(user=user)
                except Payments.DoesNotExist:
                    payments = 'No Records'
                return render(request,
                    'update.html',
                    {
                        'payments': payments,
                        'gym_form': gym_form,
                        'info_form': info_form,
                        'user': user,
                        'subs_end_today_count': get_notification_count(),
                    })
    elif request.method == 'POST' and request.POST.get('info'):
        member = Member.objects.get(pk=id)
        member.first_name = request.POST.get('first_name')
        member.last_name = request.POST.get('last_name')
        member.dob = request.POST.get('dob')

        # for updating photo
        if 'photo' in request.FILES:
            myfile = request.FILES['photo']
            fs = FileSystemStorage(base_url="")
            photo = fs.save(myfile.name, myfile)
            member.photo = fs.url(photo)
        model_save(member)

        user = Member.objects.get(pk=id)
        gym_form = UpdateMemberGymForm(initial={
                                'registration_date': user.registration_date,
                                'registration_upto': user.registration_upto,
                                'subscription_type': user.subscription_type,
                                'subscription_period': user.subscription_period,
                                'amount': user.amount,
                                'fee_status': user.fee_status,
                                'batch': user.batch,
                                'stop': user.stop,
                                })

        info_form = UpdateMemberInfoForm(initial={
                                'first_name': user.first_name,
                                'last_name': user.last_name,
                                'dob': user.dob,
                                })

        try:
            payments = Payments.objects.filter(user=user)
        except Payments.DoesNotExist:
            payments = 'No Records'

        return render(request,
            'update.html',
            {
                'payments': payments,
                'gym_form': gym_form,
                'info_form': info_form,
                'user': user,
                'updated': 'Record Updated Successfully',
                'subs_end_today_count': get_notification_count(),
            })
    else:
        user = Member.objects.get(pk=id)

        if len(Payments.objects.filter(user=user)) > 0:
            payments = Payments.objects.filter(user=user)
        else:
            payments = 'No Records'
        gym_form = UpdateMemberGymForm(initial={
                                'registration_date': user.registration_date,
                                'registration_upto': user.registration_upto,
                                'subscription_type': user.subscription_type,
                                'subscription_period': user.subscription_period,
                                'amount': user.amount,
                                'fee_status': user.fee_status,
                                'batch': user.batch,
                                'stop': user.stop,
                                })

        info_form = UpdateMemberInfoForm(initial={
                                'first_name': user.first_name,
                                'last_name': user.last_name,
                                'dob': user.dob,
                                })
        return render(request,
                        'update.html',
                        {
                            'payments': payments,
                            'gym_form': gym_form,
                            'info_form': info_form,
                            'user': user,
                            'subs_end_today_count': get_notification_count(),
                        }
                    )
