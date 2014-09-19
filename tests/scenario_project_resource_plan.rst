===============================
Project Resource Plan Scenario
===============================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()
    >>> now = datetime.datetime.now()
    >>> def add_days_without_weekend(date, days):
    ...     result = date + relativedelta(days=days)
    ...     daygenerator = (date + datetime.timedelta(x + 1) for x in xrange(
    ...         (result - date).days))
    ...     add = sum(1 for day in daygenerator if day.weekday() > 4)
    ...     result = result + relativedelta(days=add)
    ...     while result.weekday() > 4:
    ...         result += relativedelta(days=add)
    ...     return result

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install project_invoice::

    >>> Module = Model.get('ir.module.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'project_resource_plan'),
    ...     ])
    >>> Module.install([module.id], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point='.')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create party::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create employees::

    >>> Employee = Model.get('company.employee')
    >>> employee = Employee()
    >>> party = Party(name='Employee')
    >>> party.save()
    >>> employee.party = party
    >>> employee.company = company
    >>> employee.save()

    >>> second_employee = Employee()
    >>> party = Party(name='Second Employee')
    >>> party.save()
    >>> second_employee.party = party
    >>> second_employee.company = company
    >>> second_employee.save()

Configure Resources::

    >>> Config = Model.get('resource.configuration')
    >>> IRModel = Model.get('ir.model')
    >>> model, = IRModel.find([('model', '=', 'project.work')])
    >>> config = Config(1)
    >>> config.documents.append(model)
    >>> config.save()

Create resources for employees::

    >>> Calendar = Model.get('calendar.calendar')
    >>> Resource = Model.get('resource.resource')
    >>> calendar = Calendar()
    >>> calendar.name = 'Employee'
    >>> calendar.save()
    >>> resource = Resource()
    >>> resource.name = 'Employee'
    >>> resource.calendar = calendar
    >>> resource.employee = employee
    >>> resource.save()

    >>> calendar = Calendar()
    >>> calendar.name = 'Second Employee'
    >>> calendar.save()
    >>> resource = Resource()
    >>> resource.name = 'Second Employee'
    >>> resource.calendar = calendar
    >>> resource.employee = second_employee
    >>> resource.save()

Create a Project::

    >>> ProjectWork = Model.get('project.work')
    >>> TimesheetWork = Model.get('timesheet.work')
    >>> project = ProjectWork()
    >>> work = TimesheetWork()
    >>> work.name = 'Test Resource Plan'
    >>> work.save()
    >>> project.work = work
    >>> project.type = 'project'
    >>> work = TimesheetWork()
    >>> work.name = 'Task 1'
    >>> work.save()
    >>> task = project.children.new()
    >>> task.work = work
    >>> task.type = 'task'
    >>> task.effort = 16
    >>> work = TimesheetWork()
    >>> work.name = 'Task 2'
    >>> work.save()
    >>> task = project.children.new()
    >>> task.work = work
    >>> task.type = 'task'
    >>> task.effort = 8
    >>> work = TimesheetWork()
    >>> work.name = 'Task 3'
    >>> work.save()
    >>> task = project.children.new()
    >>> task.work = work
    >>> task.type = 'task'
    >>> task.effort = 8
    >>> project.save()
    >>> task_1, task_2, task_3 = project.children

Create allocations and set predecessors and successors::

    >>> task_1 = ProjectWork(task_1.id)
    >>> allocation = task_1.allocations.new()
    >>> allocation.employee = employee
    >>> allocation.percentage = 50.0
    >>> allocation = task_1.allocations.new()
    >>> allocation.employee = second_employee
    >>> allocation.percentage = 50.0
    >>> task_1.save()
    >>> allocation = task_2.allocations.new()
    >>> allocation.employee = employee
    >>> allocation.percentage = 100.0
    >>> task_1 = ProjectWork(task_1.id)
    >>> task_2.predecessors.append(task_1)
    >>> task_2.save()
    >>> allocation = task_3.allocations.new()
    >>> allocation.employee = second_employee
    >>> allocation.percentage = 100.0
    >>> task_2 = ProjectWork(task_2.id)
    >>> task_3.predecessors.append(task_2)
    >>> task_3.save()

Plan all the tasks::

    >>> plan = Wizard('project.resource.plan')
    >>> plan.form.domain = ''
    >>> plan.form.order = ''
    >>> plan.execute('tasks')
    >>> plan.form.tasks == [task_1, task_2, task_3]
    True
    >>> plan.execute('plan')
    >>> project.reload()
    >>> project.planned_start_date_project == datetime.datetime.combine(
    ...     today, datetime.time(9, 00))
    True
    >>> project.planned_end_date_project == datetime.datetime.combine(
    ...     add_days_without_weekend(today,2), datetime.time(17, 00))
    True
    >>> task_1.reload()
    >>> task_1.planned_start_date == datetime.datetime.combine(
    ...     today, datetime.time(9, 00))
    True
    >>> task_1.planned_end_date_project == datetime.datetime.combine(
    ...     today, datetime.time(17, 00))
    True
    >>> len(task_1.bookings)
    2
    >>> task_2.reload()
    >>> task_2.planned_start_date == datetime.datetime.combine(
    ...     add_days_without_weekend(today,1), datetime.time(9, 00))
    True
    >>> task_2.planned_end_date_project == datetime.datetime.combine(
    ...     add_days_without_weekend(today,1), datetime.time(17, 00))
    True
    >>> booking, = task_2.bookings
    >>> booking.state
    u'draft'
    >>> task_3.reload()
    >>> task_3.planned_start_date == datetime.datetime.combine(
    ...     add_days_without_weekend(today,2), datetime.time(9, 00))
    True
    >>> task_3.planned_end_date == datetime.datetime.combine(
    ...     add_days_without_weekend(today,2), datetime.time(17, 00))
    True
    >>> booking, = task_3.bookings
    >>> booking.state
    u'draft'

Second employee doesn't have bookings for tomorrow::

    >>> Booking = Model.get('resource.booking')
    >>> tomorrow_start = datetime.datetime.combine(
    ...     add_days_without_weekend(today,1), datetime.time(0, 00))
    >>> tomorrow_end = datetime.datetime.combine(
    ...     add_days_without_weekend(today,1), datetime.time(23, 59))
    >>> bookings = Booking.find([
    ...     ('resource.employee', '=', second_employee.id),
    ...     ('dtstart', '>=', tomorrow_start),
    ...     ('dtend', '<=', tomorrow_end),
    ...     ])
    >>> len(bookings)
    0

Cancel a booking and check it gets recreated::

    >>> booking, = task_3.bookings
    >>> booking.click('cancel')
    >>> plan = Wizard('project.resource.plan')
    >>> plan.form.domain = ''
    >>> plan.form.order = ''
    >>> plan.form.confirm_bookings = True
    >>> plan.execute('tasks')
    >>> plan.form.tasks == [task_1, task_2, task_3]
    True
    >>> plan.execute('plan')
    >>> task_3.reload()
    >>> len(task_3.bookings)
    2
    >>> sorted([b.state for b in task_3.bookings])
    [u'canceled', u'confirmed']


Plan two tasks in the same day::

    >>> work = TimesheetWork()
    >>> work.name = 'Task 4'
    >>> work.save()
    >>> task = project.children.new()
    >>> task.work = work
    >>> task.type = 'task'
    >>> task.effort = 4
    >>> project.save()
    >>> work = TimesheetWork()
    >>> work.name = 'Task 5'
    >>> work.save()
    >>> task = project.children.new()
    >>> task.work = work
    >>> task.type = 'task'
    >>> task.effort = 4
    >>> project.save()
    >>> _, _, _, task_4, task_5 = project.children
    >>> allocation = task_4.allocations.new()
    >>> allocation.employee = second_employee
    >>> allocation.percentage = 100.0
    >>> task_1 = ProjectWork(task_1.id)
    >>> task_4.predecessors.append(task_1)
    >>> task_4.save()
    >>> allocation = task_5.allocations.new()
    >>> allocation.employee = second_employee
    >>> allocation.percentage = 100.0
    >>> task_1 = ProjectWork(task_1.id)
    >>> task_5.predecessors.append(task_1)
    >>> task_5.save()
    >>> plan = Wizard('project.resource.plan')
    >>> plan.form.domain = ''
    >>> plan.form.order = ''
    >>> plan.form.confirm_bookings = True
    >>> plan.execute('tasks')
    >>> plan.execute('plan')
    >>> task_4.reload()
    >>> task_4.planned_start_date == datetime.datetime.combine(
    ...     add_days_without_weekend(today,1), datetime.time(9, 00))
    True
    >>> task_4.planned_end_date_project == datetime.datetime.combine(
    ...     add_days_without_weekend(today,1), datetime.time(13, 00))
    True
    >>> task_5.reload()
    >>> task_5.planned_start_date == datetime.datetime.combine(
    ...     add_days_without_weekend(today,1), datetime.time(13, 00))
    True
    >>> task_5.planned_end_date_project == datetime.datetime.combine(
    ...     add_days_without_weekend(today,1), datetime.time(17, 00))
    True

Open the plan wizard with a domain::

    >>> plan = Wizard('project.resource.plan')
    >>> plan.form.domain = '[["work.rec_name", "=", "Task 4"]]'
    >>> plan.form.order = ''
    >>> plan.execute('tasks')
    >>> plan.form.tasks == [task_4]
    True
