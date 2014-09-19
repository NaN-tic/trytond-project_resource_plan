# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from dateutil.relativedelta import relativedelta
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, PYSONDecoder, PYSONEncoder
from trytond.wizard import Wizard, StateAction, StateView, Button
from trytond.rpc import RPC

__all__ = ['Work', 'Allocation', 'PredecessorSuccessor',
    'ProjectResourcePlanStart', 'ProjectResourcePlanTasks',
    'ProjectResourcePlan']

__metaclass__ = PoolMeta


class Work:
    __name__ = 'project.work'

    predecessors = fields.Many2Many('project.predecessor_successor',
        'successor', 'predecessor', 'Predecessors',
        domain=[
            ('id', '!=', Eval('id')),
            ],
        states={
            'invisible': Eval('type') != 'task',
            }, depends=['type', 'id'])
    successors = fields.Many2Many('project.predecessor_successor',
        'predecessor', 'successor', 'Successors',
        domain=[
            ('id', '!=', Eval('id')),
            ],
        states={
            'invisible': Eval('type') != 'task',
            }, depends=['type', 'id'])
    allocations = fields.One2Many('project.allocation', 'work', 'Allocations',
        states={
            'invisible': Eval('type') != 'task',
            }, depends=['type'])
    bookings = fields.One2Many('resource.booking', 'document', 'Bookings',
        states={
            'invisible': Eval('type') != 'task',
            }, depends=['type'])
    expected_end_date = fields.DateTime('Expected End Date',
        states={
            'invisible': Eval('type') != 'task',
        },
        depends=['type'])
    planned_start_date = fields.DateTime('Planned Start Date',
        states={
            'invisible': Eval('type') != 'task',
        },
        depends=['type'])
    planned_end_date = fields.DateTime('Planned End Date',
        states={
            'invisible': Eval('type') != 'task',
        },
        depends=['type'])
    planned_start_date_project = fields.Function(fields.DateTime(
            'Planned Start Date',
            states={
                'invisible': Eval('type') != 'project',
            },
            depends=['type']),
        'get_project_dates')
    planned_end_date_project = fields.Function(fields.DateTime(
            'Planned End Date',
            states={
                'invisible': Eval('type') != 'project',
            },
            depends=['type']),
        'get_project_dates')
    expected_end_date_project = fields.Function(fields.DateTime(
            'Expected End Date',
            states={
                'invisible': Eval('type') != 'project',
            },
            depends=['type']),
        'get_project_dates', setter='set_expected_end_date_project')

    assigned_employee = fields.Function(fields.Many2One('company.employee',
            'Assigned'), 'get_assigned_employee',
        setter='set_assigned_employee', searcher='search_assigned_employee')

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        cls._error_messages.update({
                'no_resource_found': 'No resource found for the employee "%s"',
                })

    @property
    def scheduled(self):
        return any(b.state == 'confirmed' for b in self.bookings)

    @classmethod
    @ModelView.button
    def schedule(cls, works, done_works=None):
        pool = Pool()
        Resource = pool.get('resource.resource')
        today = datetime.datetime.now()
        if done_works is None:
            done_works = set()
        for work in works:
            if work.id in done_works or work.scheduled:
                continue
            planned_start = None
            planned_end = None
            predecessors = list(work.predecessors)
            if predecessors:
                cls.schedule(predecessors, done_works)
            for task in predecessors:
                if not planned_start:
                    planned_start = task.planned_end_date
                if task.planned_end_date:
                    planned_start = max(planned_start, task.planned_end_date)
            if planned_start and planned_start.time() >= task.company.day_ends:
                tomorrow = planned_start + relativedelta(days=1)
                #Skip saturdays and sundays
                while tomorrow.weekday() > 4:
                    tomorrow += relativedelta(days=1)
                planned_start = datetime.datetime.combine(tomorrow,
                    task.company.day_starts)
            if not work.allocations or not work.effort:
                continue

            start = planned_start or today

            for allocation in work.allocations:
                effort = work.effort * (allocation.percentage / 100)
                resources = Resource.search([
                        ('employee', '=', allocation.employee.id),
                        ], limit=1)
                if not resources:
                    cls.raise_user_error('no_resource_found',
                        allocation.employee.rec_name)
                resource, = resources
                bookings = resource.book_hours(start, effort)
                s, e = resource.book_interval(bookings)
                if planned_start and planned_start.date() == s.date():
                    #Book interval give us more information about time
                    planned_start = s
                planned_start = planned_start and min(planned_start, s) or s
                planned_end = planned_end and max(planned_end, e) or e
                resource.book(bookings, 'project.work,%s' % work.id)

            work.planned_end_date = planned_end
            work.planned_start_date = planned_start
            work.save()
            done_works.add(work.id)

    @classmethod
    def get_project_dates(cls, works, names):
        result = {}
        for name in names:
            result[name] = {}.fromkeys([w.id for w in works], None)

        for work in works:
            for child in cls.search([('parent', 'child_of', [w.id])]):
                for name in names:
                    func = min if 'start' in name else max
                    fname = name[:-8]
                    current = result[name][work.id]
                    value = getattr(child, fname)
                    if not current:
                        current = value
                    if value:
                        result[name][work.id] = func(current, value)
        return result

    @classmethod
    def set_expected_end_date_project(cls, works, name, value):
        childs = cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ])
        cls.write(childs, {
                'expected_end_date': value,
                })

    def get_assigned_employee(self, name):
        if self.allocations:
            return self.allocations[0].employee.id

    @classmethod
    def set_assigned_employee(cls, works, name, value):
        Allocation = Pool().get('project.allocation')
        Allocation.delete([allocation for work in works
                for allocation in work.allocations])
        if value:
            to_create = []
            for work in works:
                to_create.append({
                        'employee': value,
                        'work': work.id,
                        })
            Allocation.create(to_create)

    @classmethod
    def search_assigned_employee(cls, name, clause):
        if clause[2] is None:
            return [('allocations',) + tuple(clause[1:])]
        return [('allocations.employee',) + tuple(clause[1:])]


class PredecessorSuccessor(ModelSQL):
    'Predecessor - Successor'
    __name__ = 'project.predecessor_successor'
    predecessor = fields.Many2One('project.work', 'Predecessor',
            ondelete='CASCADE', required=True, select=True)
    successor = fields.Many2One('project.work', 'Successor',
            ondelete='CASCADE', required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(PredecessorSuccessor, cls).__setup__()
        cls.__rpc__.update({
            'read': RPC(True),
            'search': RPC(True),
            'search_read': RPC(True),
            })


class Allocation(ModelSQL, ModelView):
    'Allocation'
    __name__ = 'project.allocation'
    _rec_name = 'employee'
    employee = fields.Many2One('company.employee', 'Employee', required=True,
            select=True, ondelete='CASCADE')
    work = fields.Many2One('project.work', 'Work', required=True,
            select=True, ondelete='CASCADE')
    percentage = fields.Float('Percentage', digits=(16, 2), required=True,
        domain=[('percentage', '>', 0.0)])


class ProjectResourcePlanStart(ModelView):
    'Project Resource Plan Start'
    __name__ = 'project.resource.plan.start'

    view_search = fields.Many2One('ir.ui.view_search', 'Search',
        domain=[
            ('model', '=', 'project.work'),
            ])
    domain = fields.Char('Domain')
    order = fields.Char('Order')
    delete_drafts = fields.Boolean('Delete drafts', help='If marked all the '
        'draft bookings will be deleted.')
    confirm_bookings = fields.Boolean('Confirm Bookings', help='If marked the '
        'generated bookings will be confirmed.')

    @staticmethod
    def default_delete_drafts():
        return True

    @fields.depends('view_search')
    def on_change_with_domain(self):
        return self.view_search.domain if self.view_search else None


class ProjectResourcePlanTasks(ModelView):
    'Project Resource Plan Tasks'
    __name__ = 'project.resource.plan.tasks'

    tasks = fields.Many2Many('project.work', None, None, 'Tasks To Schedule',
        domain=[
            ('type', '=', 'task'),
            ])


class ProjectResourcePlan(Wizard):
    'Project Resource Plan'
    __name__ = 'project.resource.plan'

    start = StateView('project.resource.plan.start',
        'project_resource_plan.resource_plan_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'tasks', 'tryton-ok', default=True),
            ])
    tasks = StateView('project.resource.plan.tasks',
        'project_resource_plan.resource_plan_tasks_view_form', [
            Button('Back', 'start', 'tryton-go-previous'),
            Button('Ok', 'plan', 'tryton-ok', default=True),
            ])
    plan = StateAction('project_resource_plan.act_project_allocation_tree')

    def _execute(self, state_name):
        result = super(ProjectResourcePlan, self)._execute(state_name)
        if state_name == 'tasks' and self.start.domain:
            #Ensure that the view domain respects the start domain
            domain = result['view']['fields_view']['fields']['tasks']['domain']
            decoder = PYSONDecoder()
            domain = decoder.decode(domain)
            view_domain = decoder.decode(self.start.domain)
            domain.extend(view_domain)
            domain = PYSONEncoder().encode(domain)
            result['view']['fields_view']['fields']['tasks']['domain'] = domain
        return result

    def default_tasks(self, fields):
        pool = Pool()
        Work = pool.get('project.work')
        order = None
        domain = []
        if self.start.domain:
            domain = PYSONDecoder().decode(self.start.domain)
        if self.start.order:
            order = PYSONDecoder().decode(self.start.order)
        domain.append(('type', '=', 'task'))
        tasks = Work.search(domain, order=order)
        return {'tasks': [t.id for t in tasks]}

    def do_plan(self, action):
        pool = Pool()
        Work = pool.get('project.work')
        Booking = pool.get('resource.booking')

        if self.start.delete_drafts:
            to_delete = Booking.search([
                    ('state', '=', 'draft'),
                    ])
            if to_delete:
                Booking.cancel(to_delete)
                Booking.delete(to_delete)

        tasks = list(self.tasks.tasks)
        Work.schedule(tasks)
        if self.start.confirm_bookings:
            to_confirm = []
            for task in tasks:
                to_confirm.extend(list(task.bookings))
            if to_confirm:
                Booking.confirm(to_confirm)
        return action, {'res_id': [x.id for x in tasks]}
