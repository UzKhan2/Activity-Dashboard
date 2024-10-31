const ShowsGrid = () => {
    const [shows, setShows] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState(null);

    React.useEffect(() => {
        fetch('/api/shows')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                setShows(data);
                setLoading(false);
            })
            .catch(error => {
                console.error('Error fetching shows:', error);
                setError(error.message);
                setLoading(false);
            });
    }, []);

    if (loading) {
        return (
            <div className="loading-container">
                <div className="loading-message">Loading shows...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="error-message">
                Error loading shows: {error}
            </div>
        );
    }

    if (!shows.length) {
        return (
            <div className="no-content-message">
                No shows found. Start watching some shows to see them here!
            </div>
        );
    }

    return (
        <div className="media-grid">
            {shows.map((show, index) => (
                <ShowCard key={`show-${index}-${show.title}`} show={show} />
            ))}
        </div>
    );
};

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('shows-grid');
    if (container) {
        const root = ReactDOM.createRoot(container);
        root.render(<ShowsGrid />);
    }
});