const ShowCard = ({ show }) => {
    const [imageError, setImageError] = React.useState(false);
    
    return (
        <div className="media-card">
            <div className="media-poster">
                {!imageError && show.poster_url ? (
                    <img 
                        src={show.poster_url}
                        alt={`${show.title} poster`}
                        onError={() => setImageError(true)}
                    />
                ) : (
                    <div className="placeholder-poster">
                        <img 
                            src={`/api/placeholder/200/300`}
                            alt={`Placeholder for ${show.title}`}
                            className="w-full h-full object-cover"
                        />
                    </div>
                )}
            </div>
            <div className="media-info">
                <h3 className="media-title">{show.title}</h3>
                <div className="media-meta">
                    {show.year && <span>{show.year} • </span>}
                    <span>{show.episodes_watched} episodes watched</span>
                </div>
                {show.last_watched_at && (
                    <div className="media-meta">
                        Last watched: {new Date(show.last_watched_at).toLocaleDateString()}
                    </div>
                )}
                {show.genres && show.genres.length > 0 && (
                    <div className="media-meta">
                        {show.genres.join(', ')}
                    </div>
                )}
            </div>
        </div>
    );
};