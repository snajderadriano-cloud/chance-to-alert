import yaml
with open('config/channels.yaml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
for ch in data['channels']:
    print(f"{ch['channel_type']:25s} | w={ch['reliability_weight']:.2f} | @{ch.get('username','???'):25s} | {ch['name']}")
print('--- Total:', len(data['channels']), 'channels ---')
