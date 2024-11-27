import React, { useState } from 'react';
import { GitBranch, GitCommit, GitPullRequest, MessageCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const GitHubActivity = ({ activities }) => {
  const [activeFilter, setActiveFilter] = useState('all');

  // Calculate stats
  const stats = {
    total: activities.length,
    pushes: activities.filter(a => a.type === 'PushEvent').length,
    creates: activities.filter(a => a.type === 'CreateEvent').length,
    issues: activities.filter(a => a.type === 'IssuesEvent').length
  };

  // Filter activities based on active filter
  const filteredActivities = activities.filter(activity => 
    activeFilter === 'all' || activity.type === activeFilter
  );

  // Get icon based on event type
  const getEventIcon = (type) => {
    switch(type) {
      case 'PushEvent':
        return <GitCommit className="w-4 h-4" />;
      case 'CreateEvent':
        return <GitBranch className="w-4 h-4" />;
      case 'IssuesEvent':
        return <MessageCircle className="w-4 h-4" />;
      case 'PullRequestEvent':
        return <GitPullRequest className="w-4 h-4" />;
      default:
        return null;
    }
  };

  // Format date to be more readable
  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="space-y-8">
      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-lg font-medium">Total Activities</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats.total}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-lg font-medium">Push Events</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats.pushes}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-lg font-medium">Creates</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats.creates}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="p-4">
            <CardTitle className="text-lg font-medium">Issues</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats.issues}</p>
          </CardContent>
        </Card>
      </div>

      {/* Filter Buttons */}
      <div className="flex flex-wrap gap-2 p-4 bg-gray-800 rounded-lg">
        {['all', 'PushEvent', 'CreateEvent', 'IssuesEvent'].map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            className={`px-4 py-2 rounded-md transition-colors ${
              activeFilter === filter 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
            }`}
          >
            {filter === 'all' ? 'All Events' : filter.replace('Event', '')}
          </button>
        ))}
      </div>

      {/* Activity List */}
      <div className="space-y-4">
        {filteredActivities.map((activity, index) => (
          <Card key={`${activity.type}-${index}`} className="transition-all hover:shadow-lg">
            <CardContent className="p-6">
              {/* Activity Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  {getEventIcon(activity.type)}
                  <span className="text-sm font-medium bg-blue-600 text-white px-2 py-1 rounded">
                    {activity.type.replace('Event', '')}
                  </span>
                </div>
                <span className="text-sm text-gray-400">
                  {formatDate(activity.date)}
                </span>
              </div>

              {/* Repository Link */}
              <a 
                href={activity.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-lg font-semibold hover:text-blue-500 transition-colors"
              >
                {activity.repo}
              </a>

              {/* Event Specific Content */}
              {activity.type === 'PushEvent' && activity.commits && (
                <div className="mt-4 space-y-2">
                  {activity.commits.map((commit, i) => (
                    <div key={i} className="pl-4 border-l-2 border-gray-700 py-2">
                      <a
                        href={commit.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-gray-300 hover:text-blue-400 transition-colors"
                      >
                        {commit.message}
                      </a>
                    </div>
                  ))}
                </div>
              )}

              {activity.type === 'IssuesEvent' && (
                <div className="mt-4">
                  <span className="text-sm">
                    {activity.action}:{' '}
                    <a
                      href={activity.issue.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300"
                    >
                      {activity.issue.title}
                    </a>
                  </span>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default GitHubActivity;