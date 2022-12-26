# Drawing Test - Django-based comparative judgement for art assessment
# Copyright (C) 2021  Steve and Ray Heil

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index.html'),
    path('index/', views.index, name='index.html'),
    path('compare/<group>/', views.compare, name='compare.html'),
    path('compare/', views.compare, name='compare.html'),
    path('comparisons/<group>/', views.comparisons, name='comparison_list.html'),
    path('stats/<group>/', views.stats, name='stats'),
    path('item/<int:pk>/', views.item_detail, name='item_detail.html'),
    path('group/<int:pk>/', views.group_view, name='group_view'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout')
]