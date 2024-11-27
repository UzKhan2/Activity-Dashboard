const ShowsGrid = () => {
    const [shows, setShows] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState(null);

    React.useEffect(() => {
        const fetchShows = async () => {
            try {
                const response = await fetch('/api/shows');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                console.log('Fetched shows:', data);
                setShows(data);
            } catch (err) {
                console.error('Error fetching shows:', err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchShows();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <div className="text-lg">Loading shows...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                Error loading shows: {error}
            </div>
        );
    }

    if (!shows.length) {
        return (
            <div className="p-4 text-center">
                No shows found. Start watching some shows to see them here!
            </div>
        );
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 p-6">
            {shows.map((show, index) => (
                <ShowCard key={`${show.title}-${index}`} show={show} />
            ))}
        </div>
    );
};

const ShowCard = ({ show }) => {
    const defaultImage = '/api/placeholder/300/450';
    const [imageError, setImageError] = React.useState(false);

    return (
        <div className="bg-gray-800 rounded-lg overflow-hidden shadow-lg transition-transform duration-300 hover:-translate-y-1">
            <div className="relative aspect-[2/3] overflow-hidden">
                <img
                    src={!imageError ? (show.poster_url || defaultImage) : defaultImage}
                    alt={`${show.title} poster`}
                    onError={() => setImageError(true)}
                    className="w-full h-full object-cover"
                />
            </div>
            <div className="p-4">
                <h3 className="text-lg font-semibold mb-2">{show.title}</h3>
                <div className="text-sm text-gray-400 space-y-1">
                    {show.year && (
                        <div>Year: {show.year}</div>
                    )}
                    <div>Episodes: {show.episodes_watched} watched</div>
                    {show.last_watched_at && (
                        <div>
                            Last watched: {new Date(show.last_watched_at).toLocaleDateString()}
                        </div>
                    )}
                    {show.genres && show.genres.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                            {show.genres.map((genre) => (
                                <span 
                                    key={genre}
                                    className="px-2 py-1 text-xs bg-gray-700 rounded-full"
                                >
                                    {genre}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};