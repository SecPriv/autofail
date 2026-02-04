To be able to test websites served through HTTPS and that embed cross-origin iframes in Android, you must perform this setup. You need a rooted Android device or emulator.

If it's your first time performing this test, you should perform the one time setup first. 

Then each time you want to test you must:

```
- Reboot the device 
- run the script ./frida.sh
- run the script ./network_setup.sh
```

It is important to run the bash scripts in the correct order.

Now you can run the orchestrator.py script which will handle opening the test pages and sending the results to the database. You must run the orchestrator.py with root permission.



```bash
cd server
sudo -E python3 orchestrator.py
```

In the orchestrator you can use the command `browser browser_package` to launch a browser and attach the frida script to it. The frida script will attach automatically to any password manager service started.

Then you can run the `test` command to start the tests. You will find the results in the SQL database in `server/results.db`.

You can find the explanation of what the setup scripts do later in this page.

## One time setup

### certificate generation

To create the certificate:

```bash
mkcert -install
mkcert a.com b.com localhost 127.0.0.1
```

You need your Android device to trust our certification authority. To find the certification authority certificate file, run:

```bash
mkcert -CAROOT
```

Push the certificate to the Android device:

```bash
adb push /path/to/authority/rootCA.pem /sdcard/Download/
```

Now, install the certificate in the device. Open **Settings** and search for **CA Certificate**. Select the `rootCA.pem` file pushed previously.

### Password manager entries

For each password manager to test, create these credentials:

Website: a.com
Username: a@mail.com
Password: aaaapassword

Website: b.com
Username: b@mail.com
Password: bbbbpassword

## Setup scripts

### Frida

The `firda.sh` script simply pushes the frida server to the devices and runs it.
To avoid detection the frida server executable has been renamed to `simple_process`.
It is possible to get an error from the frida server. You can run `pm uninstall com.google.android.art` as root in the device's shell to solve it.

### Networking

The `network_setup.sh` script performs multiple things.

#### Making the certifcate a **System credential**

In the one time setup the certification authority certificate was installed as a **User credential**. Most of the browsers only use **System credentials**. 

To make your certificate a System certificate, follow these steps (the script.sh was written by Tim Perry from [HTTP Toolkit](https://httptoolkit.com/blog/android-14-install-system-ca-certificate/)):

```bash
adb push setup_files/script.sh /data/local/tmp
adb shell
```

Now in the device's shell:

```bash
su
cd /data/local/tmp
chmod +x script.sh
./script.sh
```

At this point, the custom certificate should appear under **System credentials**

#### Domain resolution

The device needs to resolve `a.com` and `b.com` to `127.0.0.1`. To do so, you can change the content of the `/system/etc/hosts` file. The `system` is write-only only so you need to perform some additional steps to overwrite the file, in a similar fashion on how the script used in the previous section does it.

In the device, create a temporary directory and copy the content of `/system/etc/` into it:

```bash
su
mkdir /data/local/tmp/etc-tmp
cp -r /system/etc/. /data/local/tmp/etc-tmp/
```

Add the following lines to the `/data/local/tmp/etc-tmp/hosts` file:

```
127.0.0.1	a.com
127.0.0.1	b.com
```

Now run these commands: 

```bash
mount -t tmpfs tmpfs /system/etc/
cp -r /data/local/tmp/etc-tmp/. /system/etc/

chown root:root /system/etc/*
chmod 644 /system/etc/*
chcon u:object_r:system_file:s0 /system/etc/*
```

At this point, the devices should correctly map `a.com` and `b.com` to `127.0.0.1`.

#### Adb reverse

 Now you need to map the device's ports `8080`, `8443` and `8081` of `127.0.0.1` to your computer port `80` and `443` of `127.0.0.1`. To do so, run:

```bash
adb reverse tcp:8080 tcp:80 
adb reverse tcp:8443 tcp:443
adb reverse tcp:8081 tcp:443
```
Then you should map the device's ports `80` and `443` to the devices's port `8080`,`8443`. We need this loop because we cannot use adb reverse to directly map device's `80` or `443` to computer's `80` or `443`. But with this loop we achieve the same result.
