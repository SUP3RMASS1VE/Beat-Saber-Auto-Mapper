include("BeatSaber.jl")
using .BeatSaber

# Check if we have the right number of arguments
if length(ARGS) < 3
    println("Usage: julia mapsongs.jl <audio_file> <difficulties_file> <config_file>")
    exit(1)
end

audio_file = ARGS[1]
difficulties_file = ARGS[2]
config_file = ARGS[3]

# Read difficulties from file
difficulties = String[]
if isfile(difficulties_file)
    open(difficulties_file) do file
        for line in eachline(file)
            if !isempty(line)
                push!(difficulties, strip(line))
            end
        end
    end
else
    # Default to all difficulties if file doesn't exist
    difficulties = ["Easy", "Normal", "Hard", "Expert", "ExpertPlus"]
end

# Read config from file
ffmpeg_path = "ffmpeg"  # Default
if isfile(config_file)
    open(config_file) do file
        for line in eachline(file)
            if startswith(line, "ffmpeg_path=")
                ffmpeg_path = strip(replace(line, "ffmpeg_path=" => ""))
            end
        end
    end
end

println("Processing audio file: $(audio_file)")
println("Selected difficulties: $(join(difficulties, ", "))")
println("Using ffmpeg at: $(ffmpeg_path)")

# Map the song with the specified difficulties and ffmpeg path
BeatSaber.mapsong(audio_file, difficulties=difficulties, ffmpeg_path=ffmpeg_path)
