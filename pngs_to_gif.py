from PIL import Image
import glob

file_list = glob.glob('./hula_images/*.png')
file_list.sort()
images = []
for f in file_list:
    img = Image.open(f)
    images.append(img)

images[0].save('hula.gif',
               save_all=True,
               append_images=images[1:],
               duration = 500,
               loop=0)
