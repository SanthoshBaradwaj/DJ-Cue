import type { Song } from "@/lib/types";

// Static "popular right now" seed shown before a guest types anything, so
// the song screen never opens empty. Curated by hand, not a live chart --
// there's no free real-time trending API for these genres, so this is a
// deliberately small, well-known set per genre rather than a fabricated
// "trending" claim. `id` is null (not a real catalog id) so these never
// get treated as a live iTunes/Deezer match downstream (e.g. no BPM
// lookup gets attempted for them). The moment a guest types a character,
// this list is replaced by real search results -- unchanged behaviour.
export const TRENDING: Record<string, { title: string; artist: string }[]> = {
  punjabi: [
    { title: "295", artist: "Sidhu Moose Wala" },
    { title: "Excuses", artist: "AP Dhillon" },
    { title: "Brown Munde", artist: "AP Dhillon" },
    { title: "Lover", artist: "Diljit Dosanjh" },
  ],
  tamil: [
    { title: "Rowdy Baby", artist: "Dhanush, Dhee" },
    { title: "Arabic Kuthu", artist: "Anirudh Ravichander" },
    { title: "Vaathi Coming", artist: "Anirudh Ravichander" },
    { title: "Enjoy Enjaami", artist: "Dhee, Arivu" },
  ],
  haryanvi: [
    { title: "Teri Aankhya Ka Yo Kajal", artist: "Raju Punjabi" },
    { title: "Chhora Ganga Kinare Wala", artist: "Raju Punjabi" },
    { title: "Aali Duplicate", artist: "Raju Punjabi, Sonika Singh" },
  ],
  telugu: [
    { title: "Naatu Naatu", artist: "Rahul Sipligunj, Kaala Bhairava" },
    { title: "Oo Antava", artist: "Indravathi Chauhan" },
    { title: "Butta Bomma", artist: "Armaan Malik" },
    { title: "Saami Saami", artist: "Mounika Yadav" },
  ],
  marathi: [
    { title: "Zingaat", artist: "Ajay-Atul" },
    { title: "Apsara Aali", artist: "Ajay-Atul" },
    { title: "Khel Mandala", artist: "Ajay-Atul" },
  ],
  bollywood: [
    { title: "Kala Chashma", artist: "Amar Arshi, Badshah" },
    { title: "Kar Gayi Chull", artist: "Badshah, Fazilpuria" },
    { title: "London Thumakda", artist: "Labh Janjua" },
    { title: "Nagada Sang Dhol", artist: "Shreya Ghoshal" },
  ],
  english: [
    { title: "Uptown Funk", artist: "Bruno Mars" },
    { title: "Levitating", artist: "Dua Lipa" },
    { title: "Blinding Lights", artist: "The Weeknd" },
    { title: "Flowers", artist: "Miley Cyrus" },
  ],
  edm: [
    { title: "Titanium", artist: "David Guetta ft. Sia" },
    { title: "Wake Me Up", artist: "Avicii" },
    { title: "Animals", artist: "Martin Garrix" },
  ],
};

export function trendingFor(genreKey: string): Song[] {
  return (TRENDING[genreKey] ?? []).map((t, i) => ({
    id: `trending:${genreKey}:${i}`,
    title: t.title,
    artist: t.artist,
    genre: genreKey,
    artwork_url: null,
    album: null,
    release_date: null,
    popularity: null,
    catalog_url: null,
    duration_seconds: null,
  }));
}
