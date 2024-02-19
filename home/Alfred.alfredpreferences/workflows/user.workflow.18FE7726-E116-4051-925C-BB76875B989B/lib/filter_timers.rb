require 'json'

def get_timers
  items = Dir['timer_*.txt'].map do |file|
    time, name = File.read(file).split(', ')
    {
      uid: file,
      valid: false,
      title: "#{time} (#{name})",
      subtitle: "#{name} has #{time} left, ⌘+⏎ to remove.",
      text: {
        copy: time,
        largetype: "#{time} seconds left!"
      },
      mods: {
        cmd: {
          arg: file,
          valid: true,
          subtitle: "Remove #{name} with #{time} left"
        }
      }
    }
  end

  { items: items }.to_json
end
