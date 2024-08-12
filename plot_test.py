import pandas as pd
import matplotlib.pyplot as plt

# Create the DataFrame
df = pd.DataFrame({'x': [1, 2, 3, 4, 5], 'y': [2, 4, 6, 8, 10]})

# Plot the data
plt.plot(df['x'], df['y'])

# Add labels and title
plt.xlabel('X Axis Label')
plt.ylabel('Y Axis Label')
plt.title('Example DataFrame Plot')

# Display the plot
plt.show()
