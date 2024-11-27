const container = document.getElementById('github-activities');
const activities = JSON.parse(container.dataset.activities);
const root = ReactDOM.createRoot(container);
root.render(React.createElement(GitHubActivity, { activities: activities }));